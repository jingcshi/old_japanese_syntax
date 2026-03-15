import json
import os
import ast
import pandas as pd
from typing import Any, Dict, List, Union, Optional, Callable
from pathlib import Path
from pydantic import BaseModel
from pydantic._internal._model_construction import ModelMetaclass

def load_json(filepath: Union[str, Path]) -> Any:
    """Load JSON file and return list of documents"""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_json(data: Any, filepath: Union[str, Path]) -> None:
    """Save data to JSON file with pretty formatting"""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def save_results(df: pd.DataFrame,
                 output_dir: Union[str, Path],
                 output_run_id: str,
                 raw_output_schema: ModelMetaclass,
                 json_save_schema: ModelMetaclass,
                 input_schema: Optional[ModelMetaclass] = None,
                 doc_combinator: Optional[Callable[[BaseModel, BaseModel], BaseModel]] = None,
                 file_column: str = "file",
                 output_column: str = "output",
                 input_column: str = "input_original",
                 list_dedupe: bool = True,
                 convert_to_unified: bool = False
                 ) -> None:
    """
    Save model inference results to CSV and JSON files.
    This method makes the following assumptions:
        1. The DataFrame contains columns for filenames, model outputs, and (optionally) original inputs.
        2. The CSV file will contain the direct output of the pipeline as a serialised csv_save_schema model.
        3. The JSON file will contain the direct output plus additional metadata to form a human-readable document, as a serialised json_save_schema model.
        4. The json_save_schema document can be constructed from the csv_save_schema model and optionally additional data which can be found from the original input.
    Args:
        df: DataFrame with model inference results
        output_dir: Directory to save output files
        output_run_id: Identifier for the output run (used in filenames)
        raw_output_schema: Pydantic model for parsing raw model outputs. The CSV file will use either this model or a converted version of it.
        json_save_schema: Pydantic model for saving JSON output
        doc_combinator: (Optional) Function to combine input and output models into a document
        input_schema: (Optional) Pydantic model for original inputs
        file_column: Name of the column with filenames
        output_column: Name of the column with model outputs
        input_column: (Optional) Name of the column with original inputs
        list_dedupe: Whether to deduplicate lists in the output models
        convert_to_unified: Whether to convert outputs to unified format
    """
    df_out = df[[file_column, output_column]].copy()
    json_obj = []

    for idx, row in df.iterrows():
        try:
            filename = row[file_column]
            assert isinstance(row[output_column], str)
            assert row[output_column].strip()

            try:
                output_obj = ast.literal_eval(row[output_column])
                outputs = raw_output_schema(**output_obj)
                if convert_to_unified:
                    outputs = outputs.convert_to_unified()
                if input_schema is not None:
                    if not input_column or input_column not in row:
                        raise ValueError("input_column must be provided and exist in DataFrame when input_schema is specified.")
                    if doc_combinator is None:
                        raise ValueError("doc_combinator function must be provided when input_schema is specified.")
                    inputs = input_schema(**ast.literal_eval(row[input_column]))
                    doc = doc_combinator(inputs, outputs)
                else:
                    doc = json_save_schema(**output_obj)
                if list_dedupe:
                    outputs = outputs.list_dedupe(recursive=True)
                    doc = doc.list_dedupe(recursive=True)

            except (ValueError, SyntaxError) as e:
                print(f"Warning: Error parsing output for {filename}:\n{e}")
                # Create empty document for invalid output
                outputs = raw_output_schema()
                if convert_to_unified:
                    outputs = outputs.convert_to_unified()
                doc = json_save_schema()
        
        except Exception as e:
            print(f"Warning: Empty input or processing error for {filename}:\n{e}")
            # Create empty document for exceptions
            outputs = raw_output_schema()
            if convert_to_unified:
                outputs = outputs.convert_to_unified()
            doc = json_save_schema()

        df_out.at[idx, output_column] = str(outputs.model_dump(exclude_none=True))    
        json_obj.append(doc.model_dump())

    os.makedirs(output_dir, exist_ok=True)
    df_out.to_csv(f'{output_dir}/{output_run_id}.csv', index=False)
    save_json(json_obj, f'{output_dir}/{output_run_id}-pretty.json')