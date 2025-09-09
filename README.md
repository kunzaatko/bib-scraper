# Bib Scraper

A CLI tool designed to automate the process of scraping scholarly articles from Google Scholar and integrating them into
your Zotero account. This tool is particularly useful for researchers collecting literature for **meta-analysis**.

## Features

- **Intelligent Article Search**: Search scholarly articles using command-line queries with Google Scholar integration
- **Advanced Similarity Matching**: Uses sophisticated author and title similarity algorithms to match Google Scholar results with CrossRef metadata:
  - Author matching based on last name comparison
  - Title similarity using word overlap analysis
  - Weighted scoring (70% author, 30% title) for accurate matching
  - Abstract-based ranking for multiple matches
- **Comprehensive Metadata Enrichment**: Automatically retrieves and populates rich metadata including:
  - DOI, ISBN, ISSN identifiers
  - Full abstracts and citations
  - Publication details (journal, volume, issue, pages)
  - Author information with affiliations
  - Publisher and date information
- **PDF Download & Attachment**: Automatically downloads available PDFs and attaches them to Zotero items
- **CrossRef Integration**: Leverages CrossRef API for high-quality, structured metadata from millions of scholarly works
- **Smart Organization**: Automatically creates date-stamped Zotero collections for organized storage
- **Robust Error Handling**: Comprehensive logging of failed items to TOML files for manual review and retry
- **Flexible Configuration**: Extensive CLI options for customization including debug mode, timeouts, and item limits

## Installation

1.  **Clone the repository:**

    ```bash
    git clone https://github.com/kunzaatko/bib-scraper.git
    cd bib-scraper
    ```

2.  **Install dependencies using `uv`:**

    ```bash
    uv sync
    ```

    *(Note: You might need to install `uv` first: `pip install uv`)*

3.  **Configure Zotero API credentials:**

    Create a `.env` file in the root directory of the project based on the `.env.example` file:

    ```dotenv
    ZOTERO_API_KEY="your_api_key_here"
    ZOTERO_LIBRARY_ID="your_library_id_here"
    ZOTERO_LIBRARY_TYPE="user" # or "group"
    ZOTERO_PARENT_COLLECTION_NAME="Scholarly Articles" # Name of the parent collection in Zotero
    QUERY="your default search query" # Optional: A default search query
    ```

    *   **ZOTERO_API_KEY**: Obtain this from the [Zotero website](https://www.zotero.org/settings/keys/new).
    *   **ZOTERO_LIBRARY_ID**: Your personal user ID is available [here](https://www.zotero.org/settings/keys). For group libraries, the ID can be found by opening the group’s page (`https://www.zotero.org/groups/groupname`) and hovering over the `group settings` link.
    *   **ZOTERO_LIBRARY_TYPE**: Set to `"user"` for personal libraries or `"group"` for group libraries.
    *   **ZOTERO_PARENT_COLLECTION_NAME**: The name of the top-level collection where new date-stamped sub-collections will be created. If it doesn't exist, it will be created.
    *   **QUERY**: An optional default search query that can be overridden by the `--query` CLI argument.

## CLI Arguments

The `bib-scraper` CLI tool accepts several arguments to customize its behavior:

-   `--query`: The search query for scholarly articles. Defaults to the value from the `QUERY` environment variable if set.
    -   Type: `str`
    -   Default: `os.getenv("QUERY")`
-   `--zotero-api-key`: Your Zotero API key. Defaults to the `ZOTERO_API_KEY` environment variable.
    -   Type: `str`
    -   Default: `os.getenv("ZOTERO_API_KEY")`
-   `--zotero-library-id`: Your Zotero library ID. Defaults to the `ZOTERO_LIBRARY_ID` environment variable.
    -   Type: `str`
    -   Default: `os.getenv("ZOTERO_LIBRARY_ID")`
-   `--zotero-library-type`: Your Zotero library type (`user` or `group`). Defaults to the `ZOTERO_LIBRARY_TYPE` environment variable.
    -   Type: `str`
    -   Default: `os.getenv("ZOTERO_LIBRARY_TYPE")`
-   `--zotero-parent-collection-name`: The name of the Zotero parent collection. Defaults to the `ZOTERO_PARENT_COLLECTION_NAME` environment variable.
    -   Type: `str`
    -   Default: `os.getenv("ZOTERO_PARENT_COLLECTION_NAME")`
-   `--item-limit`: The maximum number of items to scrape.
    -   Type: `int`
    -   Default: `500`
-   `--timeout`: Maximum timeout (in seconds) for the Chrome driver when waiting for elements to load.
    -   Type: `int`
    -   Default: `10`
-   `--title-prepend-index`: Prepend the item title with the index of the item from Google Scholar.
    -   Type: `bool`
    -   Default: `True`
-   `--debug`: Enable debug mode for detailed logging.
    -   Type: `bool`
    -   Default: `False`

### Help

To see the command-line help, use the `--help` flag:

```bash
uv run bib-scraper --help
```

## Usage

Run the script from the command line using `uv run`:

```bash
uv run bib-scraper --query "your scholarly search query here"
```

**Example:**

```bash
uv run bib-scraper --query "machine learning in healthcare 2023" --item-limit 100 --debug
```

## Workflow Example

<!-- Add your workflow example here -->

## Failed Items Log

If any articles fail to be added to Zotero (e.g., no DOI found, API errors), their details will be logged to files named `failed-to-identify-items-YYYY-MM-DD.toml` and `failed-to-create-items-YYYY-MM-DD.toml` in the project root directory. You can review these files to manually add the articles to Zotero if needed.
