from .settings import settings
from groq import Groq
import csv
import json

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

def analyze_dicts(list_dicts) -> list:
    final_list = []

    for dict_ in list_dicts:
        response = call_llm(craft_prompt(dict_))
        response: dict = json.loads(response)
        final_dict = dict_ | response
        final_list.append(final_dict)

    return final_list


def main() -> None:
    csv_archive = input('Enter the full CSV filename, including .csv.')
    print('recognizing CSV...')
    info = analyze_csv(csv_archive)

    if info is None:
        return

    print("Extracting the final information ... ")
    final_list = analyze_dicts(info)

    print('All done!')

    print(final_list)

    
if __name__ == "__main__":
    main()  
