from .settings import settings
from groq import Groq

client = Groq(
    api_key=settings.GROQ_API_KEY
)

def analyze_csv(csv):
    with open(csv, 'r', encoding='utf-8') as file:
        try:
            return file.read()
        except FileNotFoundError as error:
            print(f'Archivo no encontrado: {error}')
            raise

def craft_prompt(info):
    return f"""
        Analyze the following CSV:
        {info}
        and generate a new one with the same two columns plus
        four additional ones—industry, company_size_estimate, 
        one_line_summary, and confidence—analyzing the industry, 
        estimated size, a one-line summary ready for outreach, 
        and the confidence level, respectively.
        IT ONLY RETURNS THE RESPONSE IN CSV RESPONSE FORMAT 
        WITHOUT ADDING ADDITIONAL WORDS OR ABSOLUTELY ANYTHING
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
        ]
    )
   return response.choices[0].message.content

def main() -> None:
    csv = input('Enter the full CSV filename, including .csv.')
    print('recognizing CSV...')
    info = analyze_csv(csv)
    print('All set, creating prompt.')
    prompt = craft_prompt(info)
    print('Prompt created!')
    print('returning CSV ...')
    print(call_llm(prompt))
    
if __name__ == "__main__":
    main()