# Scriptwithia

Script en Python que enriquece un CSV de empresas usando un LLM a través de la API de [Groq](https://groq.com/).

A partir de un CSV con las columnas `company_name` y `raw_description`, el modelo devuelve un CSV nuevo con esas dos columnas más cuatro adicionales:

| Columna | Descripción |
|---|---|
| `industry` | Industria o sector inferido de la empresa |
| `company_size_estimate` | Estimación del tamaño de la empresa |
| `one_line_summary` | Resumen de una línea listo para outreach |
| `confidence` | Nivel de confianza del análisis |

## Requisitos

- Python >= 3.12
- [uv](https://docs.astral.sh/uv/) para gestionar dependencias
- Una API key de Groq ([console.groq.com/keys](https://console.groq.com/keys))

## Instalación

```bash
git clone https://github.com/codewithpatrick0/Scriptwithia.git
cd Scriptwithia
uv sync
```

## Configuración

Copia el archivo de ejemplo y coloca tu API key:

```bash
cp .env.example .env
```

Luego edita `.env`:

```
GROQ_API_KEY=tu_api_key_de_groq_aqui
```

El archivo `.env` está ignorado por git y **nunca** debe subirse al repositorio.

## Uso

```bash
uv run scriptwithia
```

El script pide por consola el nombre del archivo CSV (incluyendo la extensión `.csv`) y muestra el resultado por pantalla:

```
Enter the full CSV filename, including .csv. sample_input.csv
recognizing CSV...
All set, creating prompt.
Prompt created!
returning CSV ...
company_name,raw_description,industry,company_size_estimate,one_line_summary,confidence
...
```

En el repositorio se incluye `sample_input.csv` como archivo de prueba.

## Estructura del proyecto

```
Scriptwithia/
├── src/
│   └── scriptwithia/
│       ├── __init__.py      # Marcador del paquete
│       ├── script.py        # Lógica principal: lectura, prompt y llamada al LLM
│       └── settings.py      # Carga de variables de entorno con pydantic-settings
├── sample_input.csv         # CSV de ejemplo
├── prueba.py                # Script suelto de pruebas de lectura de archivos
├── .env.example             # Plantilla de variables de entorno
└── pyproject.toml
```

### Componentes

- **`settings.py`** — define `Settings` con `pydantic-settings`, que lee `GROQ_API_KEY` desde `.env` y falla al arrancar si no está definida.
- **`script.py`** — contiene el flujo completo:
  - `analyze_csv(csv)` lee el archivo de entrada.
  - `craft_prompt(info)` arma el prompt con las instrucciones de enriquecimiento.
  - `call_llm(prompt)` llama al modelo `openai/gpt-oss-120b` en Groq.
  - `main()` orquesta los tres pasos.

## Modelo

Actualmente se usa `openai/gpt-oss-120b` a través de Groq. Se puede cambiar en `call_llm()` dentro de `src/scriptwithia/script.py`.

## Estado del proyecto

Versión base funcional. Pendiente:

- [ ] Manejo de errores más robusto (archivo inexistente, CSV mal formado, fallos de la API)
- [ ] Guardar la salida en un archivo en lugar de imprimirla por consola
- [ ] Validar que la respuesta del modelo sea un CSV válido
- [ ] Recibir la ruta del CSV por argumentos de línea de comandos en vez de `input()`
- [ ] Procesar CSV grandes por lotes en lugar de enviar el archivo completo en un solo prompt
- [ ] Tests
