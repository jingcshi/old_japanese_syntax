"""
OpenAI API Utilities

This module provides helper functions for making OpenAI API calls with robust
retry logic, error handling, and progress tracking for batch processing.
"""

import time
import random
import ast
import json
from pydantic import BaseModel, ValidationError
from pydantic._internal._model_construction import ModelMetaclass
from typing import Union, Dict, Any, Callable
from openai import OpenAI, RateLimitError, APITimeoutError, APIConnectionError, APIError
from tqdm.notebook import tqdm
import pandas as pd
from multiprocessing import Pool, cpu_count
from functools import partial
import numpy as np

class ConversationRetryError(Exception):
    """Custom exception for retryable OpenAI API errors that supports retrying with previous conversation as context.

    Attributes:
        raw_input: The raw input string that failed validation (e.g., the JSON string from LLM)
        correction_message: The error message explaining what needs to be corrected
    """
    def __init__(self, message: str, raw_input: str = None):
        """
        Initialize ConversationRetryError with message and optional raw input.

        Args:
            message: The error/correction message to show the LLM
            raw_input: The raw input that caused the validation error (will be extracted from context if not provided)
        """
        super().__init__(message)
        self.correction_message = message
        self.raw_input = raw_input

def _exists_and_valid(value: Any, schema: ModelMetaclass) -> bool:
    """Check if a value exists, is not NaN, and can be parsed by the given Pydantic schema."""
    if (value is None) or pd.isna(value):
        return False
    try:
        _ = schema(**ast.literal_eval(value))
    except Exception:
        return False
    return True

def _extract_conversation_retry_error(validation_error: ValidationError) -> ConversationRetryError:
    """
    Extract ConversationRetryError from a Pydantic ValidationError chain.

    Pydantic wraps our custom validation errors in ValidationError. This function
    searches through the error chain to find our ConversationRetryError.

    Args:
        validation_error: The Pydantic ValidationError that was raised

    Returns:
        The ConversationRetryError if found, None otherwise
    """
    # Check each individual error in the validation error
    for error_dict in validation_error.errors():
        # Pydantic stores the original exception in different places depending on error type
        # For custom validators, check the 'ctx' field
        if 'ctx' in error_dict:
            ctx = error_dict['ctx']
            if 'error' in ctx and isinstance(ctx['error'], ConversationRetryError):
                return ctx['error']

    # Also check if the __cause__ or __context__ is our error
    cause = validation_error.__cause__
    if isinstance(cause, ConversationRetryError):
        return cause

    context = validation_error.__context__
    if isinstance(context, ConversationRetryError):
        return context

    return None


def pretty_print_json(obj: Union[str, dict]) -> None:
    """
    Pretty print a JSON object with proper formatting.

    Args:
        obj: Dictionary or string representation of a dictionary
    """
    if isinstance(obj, dict) or isinstance(obj, list):
        json_obj = obj
    else:
        json_obj = ast.literal_eval(obj)
    pretty_json = json.dumps(json_obj, ensure_ascii=False, indent=4).replace('\\n', '\n')
    print(pretty_json)

def openai_api_call(
    client: OpenAI,
    api_params: Dict[str, Any],
    max_retries: int = 3,
    base_delay: float = 0.05,
    max_delay: float = 60.0
) -> Any:
    """
    Make an OpenAI API call with retry logic and error handling.

    Implements exponential backoff with jitter for rate limiting and
    handles various API errors gracefully.

    Args:
        client: OpenAI client instance
        api_params: Dictionary containing API parameters
        max_retries: Maximum number of retry attempts (default: 3)
        base_delay: Base delay in seconds for exponential backoff (default: 0.05)
        max_delay: Maximum delay in seconds between retries (default: 60.0)

    Returns:
        OpenAI API response object

    Raises:
        Exception: After all retry attempts are exhausted

    Example:
        >>> client = OpenAI()
        >>> api_params = {
        ...     "model": "gpt-4o",
        ...     "input": [
        ...         {"role": "system", "content": "You are a helpful assistant."},
        ...         {"role": "user", "content": "Hello!"}
        ...     ],
        ...     "text_format": MyPydanticModel
        ... }
        >>> response = openai_api_call(
        ...     client, api_params,
        ...     validation_callback=validate_output,
        ...     error_message_callback=get_error_message
        ... )
    """
    response = None

    for attempt in range(max_retries + 1):
        try:
            # Add a small random delay to avoid thundering herd
            if attempt > 0:
                jitter = random.uniform(0, 0.1 * base_delay)
                delay = min(base_delay * (2 ** (attempt - 1)) + jitter, max_delay)
                print(f"    Retrying in {delay:.4f} seconds (attempt {attempt + 1}/{max_retries + 1})...")
                time.sleep(delay)

            # Make the API call with structured output
            # The Pydantic validators will attach raw_input to ConversationRetryError if validation fails
            response = client.responses.parse(**api_params)

            return response

        except ValidationError as e:
            # Pydantic wraps our ConversationRetryError in ValidationError
            # Extract it and re-raise for retry handling
            conversation_err = _extract_conversation_retry_error(e)
            if conversation_err:
                raise conversation_err
            else:
                # This is a different validation error, treat as parsing error
                print(f"    Validation error: {e}")
                if attempt == max_retries:
                    raise Exception(f"Response validation failed after {max_retries + 1} attempts: {e}")

        except ConversationRetryError as e:
            print(f"    Conversation retry error: {e}")
            if attempt == max_retries:
                raise Exception(f"Retryable error after {max_retries + 1} attempts: {e}")
            # Append the previous response and error message to the conversation
            api_params['input'].append({"role": "assistant", "content": e.raw_input})
            api_params['input'].append({"role": "user", "content": e.correction_message})
            print("    Conversation context updated...")

        except RateLimitError as e:
            print(f"    Rate limit error: {e}")
            if attempt == max_retries:
                raise Exception(f"Rate limit exceeded after {max_retries + 1} attempts: {e}")
            # For rate limits, use longer delays
            delay = min(base_delay * (3 ** attempt), max_delay)
            print(f"    Rate limited. Waiting {delay:.2f} seconds...")
            time.sleep(delay)

        except (APITimeoutError, APIConnectionError) as e:
            print(f"    Connection/timeout error: {e}")
            if attempt == max_retries:
                raise Exception(f"Connection failed after {max_retries + 1} attempts: {e}")

        except APIError as e:
            print(f"    API error: {e}")
            # Some API errors are not retryable
            if "invalid" in str(e).lower() or "authentication" in str(e).lower():
                raise Exception(f"Non-retryable API error: {e}")
            if attempt == max_retries:
                raise Exception(f"API error after {max_retries + 1} attempts: {e}")

        except ValueError as e:
            print(f"    Parsing error: {e}")
            if attempt == max_retries:
                raise Exception(f"Response parsing failed after {max_retries + 1} attempts: {e}")

        except Exception as e:
            print(f"    Unexpected error: {e}")
            if attempt == max_retries:
                raise Exception(f"Unexpected error after {max_retries + 1} attempts: {e}")

    # This should never be reached, but just in case
    raise Exception("All retry attempts exhausted")


def llm_infer(
    client: OpenAI,
    df: pd.DataFrame,
    model: str,
    system_prompt: str,
    input_schema: ModelMetaclass,
    output_schema: ModelMetaclass,
    overwrite: bool = False,
    output_field: str = 'output',
    input_field: str = 'input',
    file_field: str = 'file',
    error_field: str = 'error',
    extract_metric: Callable[[BaseModel], str] = None,
    max_retries: int = 3,
    base_delay: float = 0.05,
    max_delay: float = 60.0,
    **api_args
) -> None:
    """
    Process documents using OpenAI API with robust retry logic and progress tracking.

    This function processes a DataFrame of documents, calling the OpenAI API for each
    row and updating the DataFrame with results. It includes:
    - Automatic skipping of already-processed documents
    - Progress tracking with success/error/skipped counts
    - In-place DataFrame updates
    - Customizable field names for flexibility

    Args:
        client: OpenAI client instance
        df: DataFrame containing input documents
        model: Model name to use (e.g., "gpt-4o")
        system_prompt: System prompt for the model
        schema: Pydantic schema for output parsing
        overwrite: Whether to overwrite existing results (default: False)
        output_field: Name of the output column (default: 'output')
        input_field: Name of the input column (default: 'input')
        file_field: Name of the file identifier column (default: 'file')
        error_field: Name of the error column (default: 'error')
        check_empty_input: Optional function to check if input is empty for skipping (default: None)
        extract_metric: Optional function to extract a metric from output for logging (default: None)
        max_retries: Maximum number of retry attempts for API calls (default: 3)
        base_delay: Initial delay between retries in seconds (default: 0.05)
        max_delay: Maximum delay between retries in seconds (default: 60.0)
        **api_args: Additional arguments passed to OpenAI API

    Example:
        >>> df = pd.DataFrame({
        ...     'file': ['doc1.txt', 'doc2.txt'],
        ...     'input': ['text1', 'text2']
        ... })
        >>> llm_infer(
        ...     client=OpenAI(),
        ...     df=df,
        ...     model="gpt-4o",
        ...     system_prompt="Extract policy information",
        ...     schema=PolicyMetadata,
        ...     extract_metric=lambda x: len(x.get('落户政策相关内容', ''))
        ... )
    """
    # Initialize counters
    success_count = 0
    error_count = 0
    skipped_count = 0

    def update_progress_desc(pbar: tqdm) -> None:
        """Update progress bar description with current counts"""
        desc = f"{model} | ✅ {success_count} | ❌ {error_count} | ⏭️ {skipped_count}"
        pbar.set_description(desc)

    with tqdm(total=len(df), desc=f"{model} | ✅ {success_count} | ❌ {error_count} | ⏭️ {skipped_count}") as pbar:
        for idx, row in df.iterrows():
            print(f"[{idx+1}/{len(df)}] {row.get(file_field)}: ", end='')

            # Skip if output already exists and overwrite is False
            if _exists_and_valid(row.get(output_field, None), output_schema) and not overwrite:
                print('\x1b[1m\x1b[37mskipped\x1b[0m (result already exists).')
                skipped_count += 1
                update_progress_desc(pbar)
                pbar.update()
                continue

            # Skip if input is empty
            input_obj = input_schema(**ast.literal_eval(row[input_field]))
            if input_obj.is_empty():
                print('\x1b[1m\x1b[37mskipped\x1b[0m (input empty)')
                # Update the DataFrame directly - store as JSON string
                empty_object = output_schema()
                df.at[idx, output_field] = str(empty_object.model_dump())
                df.at[idx, error_field] = None  # Clear any previous error
                skipped_count += 1
                update_progress_desc(pbar)
                pbar.update()
                continue

            try:
                api_params = {
                    "model": model,
                    "input": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": row.get(input_field)}
                    ],
                    "text_format": output_schema,
                    **api_args
                }

                # Make the API call with retry logic
                response = openai_api_call(
                    client, api_params,
                    max_retries=max_retries,
                    base_delay=base_delay,
                    max_delay=max_delay
                )

                parsed_object = response.output_parsed

                # Extract metric if function provided
                metric_msg = ""
                if extract_metric:
                    metric_msg = f"({extract_metric(parsed_object)})"

                print(f'\x1b[1m\x1b[32mcompleted\x1b[0m {metric_msg}.')

                # Update the DataFrame directly - store as JSON string for proper Unicode handling
                df.at[idx, output_field] = str(parsed_object.model_dump())
                df.at[idx, error_field] = None  # Clear any previous error
                success_count += 1

            except Exception as e:
                print(f"\x1b[1m\x1b[31mError: {e}\x1b[0m")
                df.at[idx, error_field] = f"{e}"
                error_count += 1

            # Update progress bar description and advance
            update_progress_desc(pbar)
            pbar.update()


def _process_partition(
    partition_data: tuple,
    model: str,
    system_prompt: str,
    input_schema: ModelMetaclass,
    output_schema: ModelMetaclass,
    overwrite: bool,
    output_field: str,
    input_field: str,
    file_field: str,
    error_field: str,
    extract_metric: Callable[[BaseModel], str],
    max_retries: int,
    base_delay: float,
    max_delay: float,
    api_args: dict
) -> pd.DataFrame:
    """
    Process a partition of the DataFrame in a separate process.

    This function is designed to be called by multiprocessing.Pool.
    Each worker creates its own OpenAI client and processes its partition independently.

    Args:
        partition_data: Tuple of (partition_id, partition_df)
        All other args: Same as llm_infer

    Returns:
        The processed DataFrame partition with updated output and error columns
    """
    partition_id, partition_df = partition_data

    # Create a new OpenAI client in this subprocess
    # Each process needs its own client to avoid sharing network connections
    client = OpenAI()

    # Make a copy to avoid modifying the original
    df = partition_df.copy()

    # Initialize counters for this partition
    success_count = 0
    error_count = 0
    skipped_count = 0

    print(f"\n[Partition {partition_id}] Starting processing of {len(df)} rows")

    for idx, row in df.iterrows():
        file_name = row.get(file_field, f"row_{idx}")
        print(f"[Partition {partition_id}] [{idx}] {file_name}: ", end='')

        # Skip if output already exists and overwrite is False
        if _exists_and_valid(row.get(output_field, None), output_schema) and not overwrite:
            print('\x1b[1m\x1b[37mskipped\x1b[0m (result already exists).')
            skipped_count += 1
            continue

        # Skip if input is empty
        input_obj = input_schema(**ast.literal_eval(row[input_field]))
        if input_obj.is_empty():
            print('\x1b[1m\x1b[37mskipped\x1b[0m (input empty)')
            empty_object = output_schema()
            df.at[idx, output_field] = str(empty_object.model_dump())
            df.at[idx, error_field] = None
            skipped_count += 1
            continue

        try:
            api_params = {
                "model": model,
                "input": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": row.get(input_field)}
                ],
                "text_format": output_schema,
                **api_args
            }

            # Make the API call with retry logic
            response = openai_api_call(
                client, api_params,
                max_retries=max_retries,
                base_delay=base_delay,
                max_delay=max_delay
            )

            parsed_object = response.output_parsed

            # Extract metric if function provided
            metric_msg = ""
            if extract_metric:
                metric_msg = f"({extract_metric(parsed_object)})"

            print(f'\x1b[1m\x1b[32mcompleted\x1b[0m {metric_msg}.')

            # Update the DataFrame
            df.at[idx, output_field] = str(parsed_object.model_dump())
            df.at[idx, error_field] = None
            success_count += 1

        except Exception as e:
            print(f"\x1b[1m\x1b[31mError: {e}\x1b[0m")
            df.at[idx, error_field] = f"{e}"
            error_count += 1

    print(f"\n[Partition {partition_id}] Completed: ✅ {success_count} | ❌ {error_count} | ⏭️ {skipped_count}")

    return df


def llm_infer_parallel(
    df: pd.DataFrame,
    model: str,
    system_prompt: str,
    input_schema: ModelMetaclass,
    output_schema: ModelMetaclass,
    n_partitions: int = None,
    overwrite: bool = False,
    output_field: str = 'output',
    input_field: str = 'input',
    file_field: str = 'file',
    error_field: str = 'error',
    extract_metric: Callable[[BaseModel], str] = None,
    max_retries: int = 3,
    base_delay: float = 0.05,
    max_delay: float = 60.0,
    **api_args
) -> None:
    """
    Process documents using OpenAI API with parallel processing across multiple workers.

    This function splits the DataFrame into N partitions and processes each partition
    in a separate subprocess with its own OpenAI client. Results are collected and
    merged back into the original DataFrame.

    Args:
        df: DataFrame containing input documents (will be modified in-place)
        model: Model name to use (e.g., "gpt-4o")
        system_prompt: System prompt for the model
        input_schema: Pydantic schema for input validation
        output_schema: Pydantic schema for output parsing
        n_partitions: Number of partitions/workers to use (default: cpu_count())
        overwrite: Whether to overwrite existing results (default: False)
        output_field: Name of the output column (default: 'output')
        input_field: Name of the input column (default: 'input')
        file_field: Name of the file identifier column (default: 'file')
        error_field: Name of the error column (default: 'error')
        extract_metric: Optional function to extract a metric from output for logging.
                       Note: Functions defined in Jupyter notebooks may not work due to
                       pickling limitations. Set to None for parallel processing from notebooks.
        max_retries: Maximum number of retry attempts for API calls (default: 3)
        base_delay: Initial delay between retries in seconds (default: 0.05)
        max_delay: Maximum delay between retries in seconds (default: 60.0)
        **api_args: Additional arguments passed to OpenAI API

    Example:
        >>> df = pd.DataFrame({
        ...     'file': ['doc1.txt', 'doc2.txt', ...],
        ...     'input': ['text1', 'text2', ...]
        ... })
        >>> llm_infer_parallel(
        ...     df=df,
        ...     model="gpt-4o",
        ...     system_prompt="Extract policy information",
        ...     input_schema=PolicyDocumentWithRawText3,
        ...     output_schema=PolicyDNF3A,
        ...     n_partitions=4,
        ...     extract_metric=None  # Set to None when running from notebooks
        ... )
    """
    if n_partitions is None:
        n_partitions = cpu_count()

    print(f"Starting parallel processing with {n_partitions} workers...")
    print(f"Total rows to process: {len(df)}")

    # Remove 'client' from api_args if present (each subprocess creates its own)
    if 'client' in api_args:
        print("Note: Ignoring 'client' parameter - each subprocess creates its own OpenAI client.")
        api_args = {k: v for k, v in api_args.items() if k != 'client'}

    # Check if extract_metric is picklable (won't work if defined in __main__ like notebooks)
    if extract_metric is not None:
        try:
            import pickle
            pickle.dumps(extract_metric)
        except (AttributeError, pickle.PicklingError):
            print("Warning: extract_metric function cannot be pickled (likely defined in notebook).")
            print("         Parallel processing will proceed without metric extraction.")
            extract_metric = None

    # Split dataframe into partitions
    partitions = np.array_split(df, n_partitions)
    partition_data = [(i, partition) for i, partition in enumerate(partitions)]

    print(f"Partition sizes: {[len(p) for p in partitions]}")

    # Create a partial function with all the fixed parameters
    process_func = partial(
        _process_partition,
        model=model,
        system_prompt=system_prompt,
        input_schema=input_schema,
        output_schema=output_schema,
        overwrite=overwrite,
        output_field=output_field,
        input_field=input_field,
        file_field=file_field,
        error_field=error_field,
        extract_metric=extract_metric,
        max_retries=max_retries,
        base_delay=base_delay,
        max_delay=max_delay,
        api_args=api_args
    )

    # Process partitions in parallel
    with Pool(processes=n_partitions) as pool:
        results = pool.map(process_func, partition_data)

    # Merge results back into original dataframe
    print("\nMerging results...")
    for result_df in results:
        for idx in result_df.index:
            df.at[idx, output_field] = result_df.at[idx, output_field]
            df.at[idx, error_field] = result_df.at[idx, error_field]

    print("✅ Parallel processing completed!")


def infer_with_checkpointing(
    client: OpenAI,
    df: pd.DataFrame,
    model: str,
    system_prompt: str,
    input_schema: ModelMetaclass,
    output_schema: ModelMetaclass,
    checkpoint_path: str,
    save_interval: int = 10,
    overwrite: bool = False,
    output_field: str = 'output',
    input_field: str = 'input',
    file_field: str = 'file',
    error_field: str = 'error',
    extract_metric: Callable[[BaseModel], str] = None,
    max_retries: int = 3,
    base_delay: float = 0.05,
    max_delay: float = 60.0,
    **api_args
) -> None:
    """
    Run inference with periodic checkpointing to save progress.
    """
    pass


def test_api_call(
    client: OpenAI,
    df: pd.DataFrame,
    model: str,
    system_prompt: str,
    input_schema: ModelMetaclass,
    output_schema: ModelMetaclass,
    row: int = None,
    input_field: str = 'input',
    file_field: str = 'file',
    max_retries: int = 3,
    base_delay: float = 0.05,
    max_delay: float = 60.0,
    **api_args
) -> None:
    """
    Test an OpenAI API call on a single row from a DataFrame.

    This function is useful for debugging and testing API calls before
    running the full batch processing. It displays both input and output
    in a formatted way.

    Args:
        client: OpenAI client instance
        df: DataFrame containing input documents
        model: Model name to use
        system_prompt: System prompt for the model
        schema: Pydantic schema for output parsing
        row: Row index to test (default: random row)
        input_field: Name of the input column (default: 'input')
        file_field: Name of the file identifier column (default: 'file')
        raw_text_input: Display raw text instead of pretty JSON for input (default: False)
        max_retries: Maximum number of retry attempts for API calls (default: 3)
        base_delay: Initial delay between retries in seconds (default: 0.05)
        max_delay: Maximum delay between retries in seconds (default: 60.0)
        **api_args: Additional arguments passed to OpenAI API

    Example:
        >>> test_api_call(
        ...     client=OpenAI(),
        ...     df=df,
        ...     model="gpt-4o",
        ...     system_prompt="Extract policy information",
        ...     schema=PolicyMetadata,
        ...     row=42
        ... )
    """
    if row is None:
        row = random.randint(0, len(df) - 1)

    print(f"Testing row {row}: {df.loc[row, file_field]}")
    print("\n" + "=" * 80)

    api_params = {
        "model": model,
        "input": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": df.loc[row, input_field]}
        ],
        "text_format": output_schema,
        **api_args
    }

    print("\nInput:\n")

    input_obj = input_schema(**ast.literal_eval(df.loc[row, input_field]))
    pretty_print_json(input_obj.model_dump())

    response = openai_api_call(
        client, api_params,
        max_retries=max_retries,
        base_delay=base_delay,
        max_delay=max_delay
    )

    print("\n" + "=" * 80)
    print("\nOutput:\n")
    outputs = response.output_parsed.model_dump()
    pretty_print_json(outputs)
