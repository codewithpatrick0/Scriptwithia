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
        print(f'Archivo no encontrado: {error}')
        return None

def craft_prompt(dict_company: dict):
    return f"""
    Analyze the following company information:
    {json.dumps(dict_company)}

    Based on the provided information, generate ONLY the following additional fields:

    * industry: the company's main industry.
    * estimated_company_size: the estimated size of the company.
    * one_line_summary: a concise one-line company description ready for publication.
    * confidence_level: the confidence level of the generated information.

    Do NOT include or repeat any fields from the original input.

    Return ONLY a valid JSON object containing exactly these four fields:
    industry, estimated_company_size, one_line_summary, confidence_level.

    Do not include explanations, markdown, code blocks, or any text outside the JSON object.

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
                print(f'Connection attemp {attemp} failed: {error}')
                print('Reintentando en 3 segundos ...')

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

        final_dict = dict_ | response
        final_list.append(final_dict)

    return final_list


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
    csv_archive = input('Enter the full CSV filename: ')
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

    archive_name = input('Insert the name to generate the new JSON and CSV files: ')
    print('Migrate to archive JSON ...')

    final_json = migrate_json(final_list, archive_name+'.json')

    print('Done!') if final_json is True else print('Could not migrate to JSON.')

    print('Migrate to archive CSV ...')

    final_csv = migrate_csv(final_list, archive_name+'.csv')

    print('Done!') if final_csv is True else print('Could not migrate to CSV.')
    print('Proceess completed.')

    
if __name__ == "__main__":
    main()  
