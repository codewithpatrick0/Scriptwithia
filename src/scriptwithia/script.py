from .settings import settings
from groq import (
    Groq,
    APIConnectionError,
    APITimeoutError,
    RateLimitError,
    InternalServerError,
    APIStatusError,
    APIError,
    AuthenticationError,
    PermissionDeniedError,
    NotFoundError
)

import csv
import json
import time

CONFIDENCE = {'high', 'medium', 'low'}
SIZES = {'1-10', '11-50', '51-200', '201-1000', '1000+'}
FIELDS = (
    'industry',
    'estimated_company_size',
    'one_line_summary',
    'confidence_level'
)



client = Groq(
    api_key=settings.GROQ_API_KEY
)

def analyze_csv(csv_archive) -> list:
    
    try:
        with open(csv_archive, 'r', encoding='utf-8', newline="") as file:
            lista = []
            reader = csv.DictReader(file)

            for row in reader:
                lista.append(row)

            return lista
        
    except FileNotFoundError as error:
        print(f'File not found: {error}')
        return None

def craft_prompt(dict_company: dict):
    return f"""
    Analyze the following company information:
    {json.dumps(dict_company)}

    Based on the provided information, generate ONLY the following additional fields:

    * industry: the company's main industry, in lowercase, as a short noun
      phrase of at most 3 words (example: "software development").
      Use "unknown" if the description does not allow you to infer it.

    * estimated_company_size: the estimated headcount range. You MUST answer
      with EXACTLY one of these values, copied character by character:
      "1-10", "11-50", "51-200", "201-1000", "1000+", "unknown".
      Do not add the word "employees", do not add labels such as "small",
      and do not invent a different range. If the description states an exact
      number, map it to the range that contains it (12 employees -> "11-50").
      Use "unknown" if there is no basis to estimate it.

    * one_line_summary: a concise one-line company description ready for
      publication, at most 20 words, no line breaks.

    * confidence_level: how confident you are in the fields you just generated.
      You MUST answer with EXACTLY one of these values, in lowercase:
      "high", "medium", "low".
      Use "high" only when the description states the information explicitly,
      "medium" when you inferred it from clear clues, and "low" when it is
      mostly a guess.

    Do NOT include or repeat any fields from the original input.

    Return ONLY a valid JSON object containing exactly these four fields:
    industry, estimated_company_size, one_line_summary, confidence_level.

    All four values must be plain strings. Do not include explanations,
    markdown, code blocks, or any text outside the JSON object.

        """

def call_llm(prompt):
    MAX_RETRIES = 3
    for attemp in range(1, MAX_RETRIES+1):
        try: 
            response = client.chat.completions.create(
                model='openai/gpt-oss-120b',
                messages=
                [
                    {
                    'role': 'user',
                    'content': prompt
                    }
                ],
                response_format={
                    "type": "json_object"
                }
            )
            return response.choices[0].message.content
        except (
            APIConnectionError, APITimeoutError, RateLimitError, 
            InternalServerError
            ) as error:
            if attemp < MAX_RETRIES:
                print(f'Connection attempt {attemp} failed: {error}')
                print('Retrying in 3 seconds ...')

                time.sleep(3)
            else:
                print('No more attempts; we will move on to the next row.')
                raise
        except APIStatusError as error:
            print(f'Unrecoverable API error: {error}')
            
            raise

        
def analyze_dicts(list_dicts) -> list:
    final_list = []

    for dict_ in list_dicts:
        try:
            response = call_llm(craft_prompt(dict_))
            response: dict = json.loads(response)
        except (
            AuthenticationError, PermissionDeniedError, NotFoundError
            ) as error:
            print(f'Fatal API error, aborting the run: {error}')
            raise
        except APIError as error:
            print(str(error))
            continue
        except json.JSONDecodeError as error:
            print(f'Row discarded, response is not valid JSON: {error}')
            continue        

        if not isinstance(response, dict):
            print('Row discarded, the model response is not a JSON object.')
            continue

        response = normalize(response)

        final_dict = dict_ | response
        final_list.append(final_dict)

    return final_list


def normalize(response: dict) -> dict:
    clean = {field: response.get(field) or 'unknown' for field in FIELDS}

    try:
        clean['confidence_level'] = clean['confidence_level'].strip().lower()
    except AttributeError:
        print('Unexpected value type for confidence_level in the model response.')
        clean['confidence_level'] = 'unknown'

    try:
        clean['estimated_company_size'] = clean['estimated_company_size'].strip().lower()
    except AttributeError:
        print('Unexpected value type for estimated_company_size in the model response.')
        clean['estimated_company_size'] = 'unknown'

    if clean['confidence_level'] not in CONFIDENCE:
        clean['confidence_level'] = 'unknown'
    if clean['estimated_company_size'] not in SIZES:
        clean['estimated_company_size'] = 'unknown'

    return clean


def migrate_json(final_list: list, json_name: str = "new_archive.json"):
    its_a_success = True
    try:
        if len(final_list) <= 0:
            raise IndexError('No content found to migrate to JSON.') 
        
        with open(json_name, 'w', encoding='utf-8') as file:
            json.dump(
                    final_list,
                    file,
                    indent=4,
                    ensure_ascii=False
                      )
    except TypeError as error:
        print(f'The data to be transferred is not JSON-serializable: {error}')
        its_a_success = False
        
    except OSError as error:
        print(f'Could not write JSON file: {error}')
        its_a_success = False

    except IndexError as error:
        print(str(error))
        its_a_success = False

    return its_a_success

def migrate_csv(final_list: list, csv_name: str = "new_archive.csv"):
    its_a_success = True
    try:
        fieldnames = final_list[0].keys()

        with open(csv_name, 'w', encoding='utf-8', newline="") as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)

            writer.writeheader()
            writer.writerows(final_list)

    except ValueError as error:
        print(f"Invalid CSV row: {error}")
        its_a_success = False

    except OSError as error:
            print(f'Could not write CSV file: {error}')
            its_a_success = False 

    except IndexError as error:
        print(f'No content found to migrate to CSV: {error}')
        its_a_success = False

    
    return its_a_success
    
def main() -> None:
    csv_archive = input('Enter the CSV filename WITHOUT the .csv extension: ')
    print('recognizing CSV...')
    info = analyze_csv(csv_archive+'.csv')

    if info is None:
        return

    print("Extracting the final information ... ")

    try:
        final_list = analyze_dicts(info)
    except APIError:
        print('Run aborted. Check your API key and model settings, then try again.')
        return

    print('All done!')

    archive_name = input('Name for the new JSON and CSV files, WITHOUT extension: ')
    print('Migrate to archive JSON ...')

    final_json = migrate_json(final_list, archive_name+'.json')

    print('Done!') if final_json is True else print('Could not migrate to JSON.')

    print('Migrate to archive CSV ...')

    final_csv = migrate_csv(final_list, archive_name+'.csv')

    print('Done!') if final_csv is True else print('Could not migrate to CSV.')
    print('Process completed.')

    
if __name__ == "__main__":
    main()  
