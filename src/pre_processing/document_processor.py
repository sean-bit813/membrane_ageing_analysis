import json
import fitz  # PyMuPDF
from pathlib import Path
import logging
from typing import Dict, List
import re
from llm_preprocessing_api import call_doubao_api
from section_processor import SectionProcessor


class PDFProcessor:
    def __init__(self, output_dir: Path = None):
        self.output_dir = output_dir
        if output_dir:
            output_dir.mkdir(parents=True, exist_ok=True)

    def _save_content(self, content: Dict):

        """Save extracted content to a single consolidated JSON file"""
        if not self.output_dir:
            return

        paper_id = content['paper_id']

        # Consolidate all components into a single dictionary
        consolidated_content = {
            'paper_id': paper_id,
            'metadata': content['metadata'],
            'sections': content['sections'],
            'references': content['references']
        }

        # Save as a single JSON file
        output_file = self.output_dir / f'{paper_id}_consolidated.json'

        # Use json module with indentation for readability
        import json
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(consolidated_content, f, indent=4, ensure_ascii=False)

        logging.info(f"Saved consolidated content to {output_file}")

    def process_paper(self, pdf_path: Path) -> Dict:
        """Process PDF to extract content"""
        try:
            doc = fitz.open(pdf_path)

            content = {
                'paper_id': pdf_path.stem,
                'metadata': self._extract_metadata(doc),
                'sections': self._extract_sections(doc),
                'references': self._extract_references(doc)
            }

            # Save content if output directory is specified
            self._save_content(content)

            return content

        except Exception as e:
            logging.error(f"Error processing {pdf_path}: {str(e)}")
            raise

    def _extract_metadata(self, doc: fitz.Document) -> Dict:
        """Extract metadata from first page using LLM"""

        # Get text from first page
        first_page = doc[0].get_text()
        print(first_page[:4000])
        # Construct prompt for metadata extraction
        # Construct messages for Doubao API
        messages = [
            {
                "role": "system",
                "content": "You are an expert academic metadata extraction assistant. Extract structured metadata from scientific documents."
            },
            {
                "role": "user",
                "content": f"""Extract precise metadata from the following academic document text:

                Document Text:
                    {first_page[:4000]}  # Limit context to first page
                    Extract and provide the following metadata in a strict JSON format:
                    1. Title (full, exact title)
                    2. Authors (complete list of authors)
                    3. Journal Name
                    4. Publication Year
                    5. Volume and Issue Number
                    6. Brief Abstract (if available)
                    7. Keywords
                    
                    Requirements:
                    - Use exact wording from the document
                    - Be precise and concise
                    - Return valid JSON format
                    - If any field is unclear, use an empty string
                    
                    JSON Output Format:
                    {{
                        "title": "",
                        "authors": [],
                        "journal": "",
                        "year": "",
                        "volume": "",
                        "abstract": "",
                        "keywords": ""
                    }}
                    """
                            }
                        ]

        try:
            # Call Doubao API
            response_text = call_doubao_api(messages, max_tokens=500)

            # Attempt to parse JSON response
            try:
                metadata = json.loads(response_text)
            except json.JSONDecodeError:
                # Fallback to regex extraction if JSON parsing fails
                metadata = self._fallback_metadata_extraction(first_page)

            # Validate metadata
            #metadata = self._validate_metadata(metadata, first_page)

            return metadata

        except Exception as e:
            # Fallback to regex extraction in case of any errors
            print(f"Metadata extraction error: {e}")
            return self._fallback_metadata_extraction(first_page)

    def _fallback_metadata_extraction(self, text):
        """Fallback method using regex for metadata extraction"""
        metadata = {}

        # Title extraction
        title_pattern = r'^(.*?)(?=\n[A-Z][a-z]+\s+[A-Z][a-z]+|\nAbstract|\n\d{4})'
        title_match = re.search(title_pattern, text, re.MULTILINE | re.DOTALL)
        if title_match:
            metadata['title'] = title_match.group(1).strip()

        # Authors extraction
        author_pattern = r'([A-Z][a-z]+\s+[A-Z]\.\s+[A-Z][a-z]+(?:,\s*[A-Z][a-z]+\s+[A-Z]\.\s+[A-Z][a-z]+)*)'
        author_match = re.search(author_pattern, text)
        if author_match:
            metadata['authors'] = [author.strip() for author in author_match.group(1).split(',')]

        # Year extraction
        year_pattern = r'\b(20\d{2})\b'
        year_match = re.search(year_pattern, text)
        if year_match:
            metadata['year'] = year_match.group(1)

        # Journal extraction
        journal_pattern = r'^(.*?)\s+\d+\s*\(\d{4}\)'
        journal_match = re.search(journal_pattern, text, re.MULTILINE)
        if journal_match:
            metadata['journal'] = journal_match.group(1).strip()

        return metadata

    def _extract_sections(self, doc: fitz.Document) -> Dict[str, str]:
        """
        Extract sections from two-column scientific paper with structured format.

        Parameters:
            doc (fitz.Document): Input PDF document

        Returns:
            Dict[str, str]: Extracted sections with standardized keys
        """
        section_processor = SectionProcessor()
        return section_processor.extract_sections(doc)


    def _extract_references(self, doc: fitz.Document) -> List[str]:
        """Extract references with improved pattern matching"""
        references = []
        text = ""
        for page in doc:
            text += page.get_text()

        # Find references section
        ref_section_match = re.search(r'References\s*(.*?)(?=\n\s*Appendix|\Z)',
                                      text, re.DOTALL | re.IGNORECASE)

        if ref_section_match:
            ref_text = ref_section_match.group(1)

            # Match different reference formats
            ref_patterns = [
                r'\[\d+\](.*?)(?=\[\d+\]|\Z)',  # [1] style
                r'^\d+\.\s+(.*?)(?=^\d+\.\s+|\Z)',  # 1. style
                r'\(\w+\s+et\s+al\.,\s+\d{4}\)(.*?)(?=\(\w+\s+et\s+al\.,\s+\d{4}\)|\Z)'  # (Author et al., year) style
            ]

            for pattern in ref_patterns:
                matches = re.finditer(pattern, ref_text, re.MULTILINE | re.DOTALL)
                for match in matches:
                    ref = match.group(1).strip()
                    if ref:  # Only add non-empty references
                        references.append(ref)

            if references:  # If any pattern worked, return results
                return references

            # If no patterns worked, try simple line-based splitting
            references = [line.strip() for line in ref_text.split('\n')
                          if line.strip() and len(line.strip()) > 20]

        return references


if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    # Define paths
    current_dir = Path(__file__).parent
    input_dir = current_dir.parent.parent / 'data/raw'
    output_path = current_dir.parent.parent / 'data/processed/consolidated'

    # Create processor
    processor = PDFProcessor(output_path)

    # Get all PDF files in the input directory
    pdf_files = list(input_dir.glob('*.pdf'))

    # Process each PDF
    for pdf_path in pdf_files:
        try:
            result = processor.process_paper(pdf_path)
            logging.info(f"Successfully processed {pdf_path}")
            logging.info(f"Found {len(result['sections'])} sections")
            logging.info(f"Found {len(result['references'])} references")
        except Exception as e:
            logging.error(f"Failed to process {pdf_path}: {str(e)}")