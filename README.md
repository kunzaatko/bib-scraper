<p align="center">
    <img src="./assets/logo.png" alt="A Google Scholar logo with a knife over it that signifies scraping" style="width: 45%">
</p>

# Bib Scraper

A CLI tool designed to automate the process of scraping scholarly articles from Google Scholar and integrating them into
your Zotero account. This tool is particularly useful for researchers collecting literature for **meta-analysis**.

## Features
- **Scraping**: Scrapes the specified number of top google scholar items for the given query
- **Metadata Enrichment**: Finds the metadata (authors, abstract, year, etc.) by finding a match in _CrossRef_
  - CrossRef match is made by comparing the title, authors and abstract if available. Abstract is compared as an
    embedding.
- **Download Attachments**: Automatically downloads available PDFs and attaches them to the Zotero items

## Installation

Install the tool using `uv` by running
```bash
$ uv tool install git+https://github.com/kunzaatko/bib-scraper
```

*(Note: You might need to install `uv` first: `pip install uv`)*

## Configuration

Create a `.env` file in the root directory of the project by copying the `.env.example` file and filling in the required
variables.

## Usage

Run the script from the command line using `uv tool run --from scraper bib-scraper`.

```bash
$ uv tool run --from scraper bib-scraper --query "\"SIM parameter estimation\" OR \"SIM image reconstruction algorithm\"" --item-limit 15
```

<p align="center">
    <img src="https://github.com/user-attachments/assets/2b01ba3a-e07d-4743-a81b-d118c39116d2" alt="Showcase GIF" style="width: 80%">
</p>

<details>
<summary> Full resolution showcase video </summary>
    
[full resolution output](https://github.com/user-attachments/assets/a756d4b7-b422-40aa-86e2-dab45a33562c)

</details>

To see the command-line help and all the available options, use the `--help` flag:

```bash
$ uv run bib-scraper --help
```
