# src/preprocessing/json_cleaner.py

from typing import Dict, List
import re
import json
from pathlib import Path
import logging


class JSONCleaner:
    def __init__(self):
        self.section_aliases = {
            'introduction': ['1. introduction', 'i. introduction', 'introduction'],
            'methods': ['2. materials and methods', 'experimental', 'materials and methods'],
            'results': ['3. results', 'results and discussion'],
            'discussion': ['4. discussion', 'discussion'],
            'conclusions': ['5. conclusions', 'conclusion', 'concluding remarks']
        }

    def clean_document(self, json_content: Dict) -> Dict:
        """
        Standardize and clean document JSON structure.

        Parameters:
            json_content (Dict): Raw consolidated JSON document

        Returns:
            Dict: Cleaned and standardized document structure
        """
        cleaned_doc = {
            'paper_id': self._standardize_paper_id(json_content['paper_id']),
            'metadata': self._clean_metadata(json_content['metadata']),
            'sections': self._clean_sections(json_content['sections']),
            'references': self._clean_references(json_content['references'])
        }

        return cleaned_doc

    def _standardize_paper_id(self, paper_id: str) -> str:
        """Standardize paper ID format"""
        # Remove special characters and spaces
        std_id = re.sub(r'[^\w\s-]', '', paper_id)
        # Convert to lowercase and replace spaces with underscores
        return std_id.lower().replace(' ', '_')

    def _clean_metadata(self, metadata: Dict) -> Dict:
        """
        Clean and validate metadata fields.

        Parameters:
            metadata (Dict): Raw metadata dictionary

        Returns:
            Dict: Cleaned and validated metadata
        """
        cleaned_metadata = {
            'title': self._clean_text(metadata.get('title', '')),
            'authors': [],
            'journal': self._clean_text(metadata.get('journal', '')),
            'year': self._extract_year(metadata.get('year', '')),
            'volume': self._clean_text(metadata.get('volume', '')),
            'abstract': self._clean_text(metadata.get('abstract', '')),
            'keywords': self._clean_keywords(metadata.get('keywords', []))
        }

        # Process authors
        for author in metadata.get('authors', []):
            cleaned_author = self._clean_author(author)
            if cleaned_author:
                cleaned_metadata['authors'].append(cleaned_author)

        return cleaned_metadata

    def _clean_keywords(self, keywords: List[str]) -> List[str]:
        """
        Standardize and clean keywords.

        Parameters:
            keywords (List[str]): Raw keyword list

        Returns:
            List[str]: Cleaned and standardized keywords
        """
        if not keywords:
            return []

        cleaned_keywords = []

        # Verify input type
        if isinstance(keywords, str):
            # If input is a single string, split by common delimiters
            keywords = keywords.split(';') if ';' in keywords else keywords.split(',')

        for keyword in keywords:
            if not isinstance(keyword, str):
                continue

            # Clean individual keyword while preserving complete terms
            cleaned = keyword.strip()
            cleaned = cleaned.lower()

            # Remove trailing punctuation
            cleaned = re.sub(r'[;,.]$', '', cleaned)

            # Remove excessive whitespace while preserving terms
            cleaned = ' '.join(cleaned.split())

            # Remove common prefixes while preserving the main term
            cleaned = re.sub(r'^(the|a|an)\s+', '', cleaned)

            if cleaned and len(cleaned) > 1:  # Ensure keyword is not empty or single character
                cleaned_keywords.append(cleaned)

        # Remove duplicates while preserving order
        seen = set()
        return [x for x in cleaned_keywords if not (x in seen or seen.add(x))]

    def _clean_author(self, author: str) -> Dict:
        """
        Standardize author name format and extract affiliations.

        Parameters:
            author (str): Raw author string

        Returns:
            Dict: Structured author information
        """
        author = self._clean_text(author)

        # Extract name parts
        name_parts = author.split(',')[0].strip().split()
        if not name_parts:
            return None

        author_dict = {
            'full_name': author,
            'last_name': name_parts[-1] if name_parts else '',
            'first_name': ' '.join(name_parts[:-1]) if len(name_parts) > 1 else '',
            'affiliations': []
        }

        # Extract affiliations if present
        if ',' in author:
            affiliations = [
                aff.strip()
                for aff in author.split(',')[1:]
                if aff.strip()
            ]
            author_dict['affiliations'] = affiliations

        return author_dict

    def _remove_reference_markers(self, text: str) -> str:
        """
        Remove in-text citation markers.

        Parameters:
            text (str): Input text with reference markers

        Returns:
            str: Cleaned text without reference markers
        """
        # Remove numbered citations [1], [2,3], [4-6]
        text = re.sub(r'\[\d+(?:[-,]\d+)*\]', '', text)

        # Remove author-year citations (Smith et al., 2020)
        text = re.sub(r'\([^)]*?(?:19|20)\d{2}[^)]*?\)', '', text)

        # Remove excessive spaces after cleaning
        text = re.sub(r'\s+', ' ', text)

        return text.strip()

    def _clean_sections(self, sections: Dict) -> Dict:
        """Clean and standardize section content"""
        cleaned_sections = {}

        for section_name, content in sections.items():
            # Standardize section names
            std_section_name = self._standardize_section_name(section_name)
            if std_section_name:
                # Clean section content
                cleaned_content = self._clean_text(content)
                # Remove reference markers
                cleaned_content = self._remove_reference_markers(cleaned_content)
                # Store if content is not empty
                if cleaned_content.strip():
                    cleaned_sections[std_section_name] = cleaned_content

        return cleaned_sections

    def _clean_references(self, references: List[str]) -> List[Dict]:
        """Clean and structure references"""
        cleaned_refs = []

        for ref in references:
            cleaned_ref = self._parse_reference(ref)
            if cleaned_ref:
                cleaned_refs.append(cleaned_ref)

        return cleaned_refs

    def _clean_text(self, text: str) -> str:
        """Clean text content"""
        if not text:
            return ""

        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        # Remove special characters
        text = re.sub(r'[^\w\s.,;:()\-\[\]]', '', text)
        # Standardize quotes
        text = text.replace('"', '"').replace('"', '"')

        return text.strip()

    def _standardize_section_name(self, section_name: str) -> str:
        """Map section names to standard format"""
        section_name = section_name.lower().strip()

        for std_name, aliases in self.section_aliases.items():
            if section_name in aliases:
                return std_name

        return section_name

    def _parse_reference(self, ref: str) -> Dict:
        """Parse reference string into structured format"""
        try:
            # Extract DOI if present
            doi_match = re.search(r'10\.\d{4,}/\S+', ref)
            doi = doi_match.group(0) if doi_match else None

            # Basic reference structure
            parsed_ref = {
                'text': self._clean_text(ref),
                'doi': doi,
                'year': self._extract_year(ref)
            }

            return parsed_ref

        except Exception as e:
            logging.warning(f"Error parsing reference: {str(e)}")
            return None

    def _extract_year(self, text: str) -> str:
        """Extract publication year"""
        year_match = re.search(r'(19|20)\d{2}', str(text))
        return year_match.group(0) if year_match else ""


    def _validate_cleaned_document(self, doc: Dict) -> bool:
        """
        Validate cleaned document structure and content.

        Parameters:
            doc (Dict): Cleaned document

        Returns:
            bool: True if document passes validation
        """
        required_fields = ['paper_id', 'metadata', 'sections', 'references']

        # Check required fields
        if not all(field in doc for field in required_fields):
            return False

        # Validate metadata
        if not doc['metadata'].get('title') or not doc['metadata'].get('authors'):
            return False

        # Validate sections
        if not any(doc['sections'].values()):
            return False

        return True


    def _validate_references(self, references: List[Dict]) -> List[Dict]:
        """
        Validate and filter references.

        Parameters:
            references (List[Dict]): Cleaned references

        Returns:
            List[Dict]: Validated references
        """
        validated_refs = []

        for ref in references:
            # Check minimum required fields
            if not ref.get('text'):
                continue

            # Validate year if present
            if ref.get('year'):
                try:
                    year = int(ref['year'])
                    if not (1900 <= year <= 2025):
                        ref['year'] = None
                except ValueError:
                    ref['year'] = None

            validated_refs.append(ref)

        return validated_refs

def process_corpus(input_dir: Path, output_dir: Path):
    """
    Process entire corpus with validation and error handling.

    Parameters:
        input_dir (Path): Input directory containing consolidated JSONs
        output_dir (Path): Output directory for cleaned JSONs
    """
    cleaner = JSONCleaner()

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    # Track processing statistics
    stats = {
        'total': 0,
        'successful': 0,
        'failed': 0,
        'warnings': 0
    }

    # Process each JSON file
    for json_file in input_dir.glob('*_consolidated.json'):
        stats['total'] += 1

        try:
            # Load JSON
            with open(json_file, 'r', encoding='utf-8') as f:
                doc = json.load(f)

            # Clean document
            cleaned_doc = cleaner.clean_document(doc)

            # Validate cleaned document
            if not cleaner._validate_cleaned_document(cleaned_doc):
                logging.warning(f"Document validation failed: {json_file.name}")
                stats['warnings'] += 1
                continue

            # Save cleaned version
            output_path = output_dir / f"{cleaned_doc['paper_id']}_cleaned.json"
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(cleaned_doc, f, indent=4, ensure_ascii=False)

            stats['successful'] += 1
            logging.info(f"Successfully cleaned {json_file.name}")

        except Exception as e:
            stats['failed'] += 1
            logging.error(f"Error processing {json_file.name}: {str(e)}")

    # Log summary statistics
    logging.info(f"Processing complete. Summary:")
    logging.info(f"Total files: {stats['total']}")
    logging.info(f"Successfully processed: {stats['successful']}")
    logging.info(f"Failed: {stats['failed']}")
    logging.info(f"Warnings: {stats['warnings']}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Define directories
    base_dir = Path(__file__).parent.parent.parent
    input_dir = base_dir / 'data/processed/consolidated'
    output_dir = base_dir / 'data/processed/cleaned'

    # Process corpus
    process_corpus(input_dir, output_dir)