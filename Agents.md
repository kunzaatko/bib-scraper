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
  settings from a `.env` file or command-line arguments.
- **Google Scholar Search:** Performs search at _Google Scholar_ via the `undetected_chromedriver` package.
- **Date-Stamped Collections:** Automatically creates a new sub-collection in Zotero with the current date as its name
  for each run in a different name.
- **Failed Item Logging:** Logs details of articles that could not be added to Zotero (e.g., missing DOI, Zotero API
  errors) to `failed-to-identify-items-{date}.toml` and `failed-to-create-items-{date}.toml` files.

## Technical Approach

### 1. Environment Setup
- Uses `python-dotenv` to load `ZOTERO_API_KEY`, `ZOTERO_LIBRARY_ID`, `ZOTERO_LIBRARY_TYPE`,
  `ZOTERO_PARENT_COLLECTION_NAME` and other configuration from a `.env` file.

### 2. CLI Argument Parsing
- Utilizes `argparse` to accept command-line arguments, which can override environment variables.
- Configurable CLI arguments include:
  - `--query`: Search query for scholarly articles (defaults to environment variable `QUERY`)
  - `--zotero-api-key`: Zotero API key (defaults to `ZOTERO_API_KEY`)
  - `--zotero-library-id`: Zotero library ID (defaults to `ZOTERO_LIBRARY_ID`)
  - `--zotero-library-type`: Zotero library type (defaults to `ZOTERO_LIBRARY_TYPE`)
  - `--zotero-parent-collection-name`: Parent collection name (defaults to `ZOTERO_PARENT_COLLECTION_NAME`)
  - `--item-limit`: Maximum number of items to scrape (defaults to 500)
  - `--timeout`: Maximum timeout (in seconds) for Chrome driver element loading (defaults to 10)
- Supports graceful fallback to environment variables for configuration.

### 3. Logging
- Uses Python's standard `logging` module, configured via `logging.config.dictConfig`.
- **Formatters:**
    - `onlymessage`: For console output, showing only the message.
    - `standard`: For file output, including timestamp, log level, and message.
- **Handlers:**
    - `console`: Uses `rich.logging.RichHandler` for formatted console output.
    - `file`: Uses `logging.FileHandler` to write logs to `scraper_YYYY-MM-DD.log`.
- **Loggers:** The main logger (`__name__`) is configured to output `INFO` level messages and above to both console and file.
- **Failed Item Logging:** The `log_failed_item` function writes details of failed items to TOML files (`failed-to-identify-items-{date}.toml` and `failed-to-create-items-{date}.toml`).

### 4. Source Code Operation

#### `src/scraper/__init__.py`
- Initializes the environment by loading `.env` variables.
- Exports core components: `climain` (the main CLI entry point), `item` (data structures for scholarly items), `utils` (utility functions), and `__version__`.

#### `src/scraper/cli.py`
- **Main Entry Point**: The `main` function orchestrates the entire scraping and Zotero integration process.
- **Browser Automation**:
    - Initializes `undetected_chromedriver` to interact with Google Scholar.
    - Navigates to Google Scholar, enters the search query, and handles potential reCAPTCHA challenges by prompting user intervention.
    - Scrapes search results, extracts HTML `div` elements for each article.
- **Item Processing Loop**:
    - Iterates through scraped `div` elements, creating `ScholarItem` instances.
    - Attempts to retrieve metadata for each `ScholarItem` using external APIs (e.g., CrossRef).
    - If metadata is successfully retrieved and a DOI is found, the item is prepared for Zotero.
    - Items without a DOI or failed metadata retrieval are logged to `failed-to-identify-items-{date}.toml`.
- **Zotero Integration**:
    - Batches Zotero item creation (up to 50 items per API call) using `pyzotero`.
    - Logs items that fail during Zotero creation to `failed-to-create-items-{date}.toml`.
    - Adds successfully created items to the date-stamped sub-collection.
- **Progress and Summary**: Uses `rich.progress` for visual progress tracking and provides a summary of added and failed items.

#### `src/scraper/item.py`
- **`ScholarItem` Class**: Represents a single scholarly article.
    - **Initialization**: Takes a title, optionally a Zotero client, and processes the title to identify `[book]` or `[pdf]` tags.
    - **Metadata Mapping**: `ITEM_TYPE_MAPPING` translates CrossRef item types to Zotero item types.
    - **Metadata Retrieval (`_update_from_crossref`)**:
        - Queries the CrossRef API using the article title.
        - Parses the JSON response to extract relevant metadata (title, authors, abstract, publication details, DOI, ISBN, ISSN, URL, language).
        - Dynamically updates the Zotero item template based on the detected CrossRef item type.
        - Includes helper methods (`_process_authors`, `_process_date`, `_process_abstract`) to format CrossRef data for Zotero.
    - **Error Handling**: Logs errors during CrossRef API calls and tracks failed metadata sources.

#### `src/scraper/utils.py`
- **`get_or_create_collection` Function**:
    - Interacts with the Zotero API to find an existing collection by name and optional parent.
    - If the collection does not exist, it creates a new one, supporting nested collection hierarchies.
- **`setup_zotero_client` Function**:
    - Initializes and returns a `pyzotero.Zotero` client instance.
    - Prioritizes provided arguments for Zotero library ID, type, and API key, falling back to environment variables if not provided.

### 5. Current Development Notes (TODOs)
- **`src/scraper/item.py`**:
    - `TODO: Update the alternatives with `all versions` part of the div <04-09-25>`: This indicates a need to enhance the `ScholarItem` creation or metadata retrieval to consider "all versions" links often found in Google Scholar results.
- **`src/scraper/cli.py`**:
    - `TODO: Recognize the chrome version that is used with `google-chrome --version` <04-09-25>`: The `undetected_chromedriver` currently uses a hardcoded Chrome version (`version_main=139`). This needs to be made dynamic to automatically detect the installed Chrome version.
    - `TODO: Sometimes the next button is not present on the page because the page has a different size. It should hold the index of the page and instead then search for the next index which is always on the page. <28-08-25>`: This addresses a pagination issue where the "Next" button might be missing, suggesting a more robust pagination strategy based on page indexing.
    - `NOTE: Effectively once the items are uploaded, this should not fail <04-09-25>`: This is a note about the expectation that Zotero item uploads should be reliable after initial processing.

## User Interaction
- The CLI tool will accept a search query and other configurations as arguments.
- It will print simple messages to the console indicating progress (e.g., "Searching for articles...", "Added X articles to Zotero.").
- Messages will be displayed if `failed-to-identify-items-{date}.toml` or `failed-to-create-items-{date}.toml` files are created.
- Manual reCAPTCHA solving is required for Google Scholar search if detected.
