# Environment Instructions
## Python
- Unless instructed otherwise, always use the `uv` Python environment and package manager for Python.
  - `uv run ...` for running a python script.
  - `uvx ...` for running program directly from a PyPI package.
  - `uv ... ...` for managing environments, installing packages, etc...

# Project: CLI Tool for Scholarly to Zotero Integration
## Purpose
This CLI tool will automate the process of searching for academic publications using from _Google Scholar_ and adding
them to a specified Zotero account via `pyzotero`. It will organize new entries into date-stamped sub-collections and
add rich metadata from the files. Failed additions will be logged to a TOML file for later manual review.

## Key Features
- **Configurable:** Reads Zotero API key, library ID, library type (user or group), parent collection name and other
  settings from a `.env` file.
- **Google Scholar Search:** Performs search at _Google Scholar_ via the `undetected_chromedriver` package.
- **Date-Stamped Collections:** Automatically creates a new sub-collection in Zotero with the current date as its name
  for each run in a different name.
- **Failed Item Logging:** Logs details of articles that could not be added to Zotero (e.g., missing DOI, Zotero API
  errors) to a `failed-items-{date}.toml` file.

## Technical Approach

### 1. Environment Setup
- Use `python-dotenv` to load `ZOTERO_API_KEY`, `ZOTERO_LIBRARY_ID`, `ZOTERO_LIBRARY_TYPE`,
  `ZOTERO_PARENT_COLLECTION_NAME` and other configuration from a `.env` file.

### 2. CLI Argument Parsing
- Utilize `argparse` to accept modifications for the command-line arguments of the CLI tool.
- Configurable CLI arguments include:
  - `--query`: Search query for scholarly articles (defaults to environment variable `QUERY`)
  - `--zotero-api-key`: Zotero API key (defaults to `ZOTERO_API_KEY`)
  - `--zotero-library-id`: Zotero library ID (defaults to `ZOTERO_LIBRARY_ID`)
  - `--zotero-library-type`: Zotero library type (defaults to `ZOTERO_LIBRARY_TYPE`)
  - `--zotero-parent-collection-name`: Parent collection name (defaults to `ZOTERO_PARENT_COLLECTION_NAME`)
  - `--item-limit`: Maximum number of items to scrape (defaults to 500)
- Supports graceful fallback to environment variables for configuration

### 3. Google Scholar Interaction
- Uses `undetected_chromedriver` to bypass bot detection
- Automated browser interaction with Google Scholar:
  - Navigate to Google Scholar website
  - Enter search query dynamically via CLI argument
  - Requires manual reCAPTCHA solving during initial search
- Systematic article scraping process:
  - Extract article titles using CSS selector `"h3.gs_rt"`
  - Supports pagination to retrieve multiple result pages
  - Configurable item limit (default 500 items)
- Metadata enrichment workflow:
  - Use CrossRef API to retrieve additional publication details
  - Extract DOI and other metadata (title, authors, abstract, etc.)
  - If DOI is found:
    - Prepare Zotero item template
    - Enhance item with retrieved metadata
  - If no DOI is found:
    - Log the item to `failed-items-{date}.toml`
- Error handling:
  - Graceful handling of loading and retrieval issues
  - Supports skipping items without DOI
  - Provides detailed logging of failed retrievals

### 4. Zotero Interaction
- Initialize `pyzotero.Zotero(library_id, library_type, api_key)`.
- **Collection Management:**
    - Dynamically create or retrieve collections
    - Create parent collection specified by `ZOTERO_PARENT_COLLECTION_NAME`
    - Create a date-stamped sub-collection (format: `YYYY-MM-DD`)
    - Supports nested collection hierarchy
    - Gracefully handles existing collections to prevent duplicates
- **Item Creation:**
    - Create Zotero item templates for publications with valid DOI
    - Batch item creation (up to 50 items per API call)
    - Automatically assign items to the date-stamped sub-collection
    - Metadata enrichment:
        - Populate item template with CrossRef API data
        - Add bibliographic details (title, authors, abstract, etc.)
    - Error handling:
        - Log failed item additions to `failed-items-{date}.toml`
        - Provides summary of successful and failed additions
- **Workflow Limitations:**
    - Manual reCAPTCHA solving required for Google Scholar search

## User Interaction
- The CLI tool will accept a search query as an argument.
- It will print simple messages to the console indicating progress (e.g., "Searching for articles...", "Added X articles to Zotero.").
- A message will be displayed if a `failed-items-{date}.toml` file is created.
