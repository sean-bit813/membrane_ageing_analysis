from pathlib import Path
import logging
from typing import Dict, List, Optional
from grobid_client.grobid_client import GrobidClient
import camelot
import xml.etree.ElementTree as ET
import pandas as pd
import re


class ScientificPaperProcessor:
    """
    A comprehensive processor for scientific papers utilizing GROBID and specialized tools
    for extracting structured content including metadata, sections, tables, and references.
    """

    def __init__(self, grobid_url: str = "http://localhost:8070", output_dir: Optional[Path] = None):
        """
        Initialize the processor with GROBID client and output configuration.

        Args:
            grobid_url: URL of GROBID service
            output_dir: Directory for storing processed outputs
        """
        self.grobid_client = GrobidClient(grobid_url)
        self.output_dir = output_dir
        self.logger = logging.getLogger(__name__)

        if output_dir:
            self.output_dir.mkdir(parents=True, exist_ok=True)

    def process_paper(self, pdf_path: Path) -> Dict:
        """
        Process scientific paper to extract structured content.

        Args:
            pdf_path: Path to PDF file

        Returns:
            Dictionary containing structured paper content
        """
        try:
            # Extract structured content using GROBID
            xml_content = self.grobid_client.process_pdf(
                str(pdf_path), "processFulltextDocument")
            tree = ET.fromstring(xml_content)

            # Extract components
            metadata = self._extract_metadata(tree)
            sections = self._extract_sections(tree)
            tables = self._extract_tables(pdf_path)
            references = self._extract_references(tree)

            paper_content = {
                'paper_id': pdf_path.stem,
                'metadata': metadata,
                'sections': sections,
                'tables': tables,
                'references': references
            }

            # Save if output directory specified
            if self.output_dir:
                self._save_content(paper_content)

            return paper_content

        except Exception as e:
            self.logger.error(f"Error processing {pdf_path}: {str(e)}")
            raise

    def _extract_metadata(self, tree: ET.Element) -> Dict:
        """Extract metadata from GROBID XML"""
        header = tree.find('.//teiHeader/fileDesc/titleStmt')
        authors = []
        for author in tree.findall('.//teiHeader//author'):
            author_name = []
            for name_part in author.findall('.//persName//*'):
                if name_part.text:
                    author_name.append(name_part.text.strip())
            if author_name:
                authors.append(' '.join(author_name))

        return {
            'title': header.findtext('.//title'),
            'authors': authors,
            'abstract': tree.findtext('.//abstract'),
            'keywords': [kw.text for kw in tree.findall('.//keyword')],
            'journal': tree.findtext('.//journal-title'),
            'doi': tree.findtext('.//idno[@type="DOI"]'),
            'publication_date': tree.findtext('.//publicationStmt/date')
        }

    def _extract_sections(self, tree: ET.Element) -> Dict:
        """Extract sections from GROBID XML"""
        sections = {}
        for div in tree.findall('.//body//div'):
            head = div.findtext('./head')
            if head:
                # Combine all text content in section
                text_parts = []
                for p in div.findall('.//p'):
                    if p.text:
                        text_parts.append(p.text.strip())
                sections[head.strip()] = '\n'.join(text_parts)
        return sections

    def _extract_tables(self, pdf_path: Path) -> List[Dict]:
        """Extract tables using Camelot"""
        tables = camelot.read_pdf(str(pdf_path), pages='all')
        extracted_tables = []

        for table in tables:
            # Extract table caption if available
            caption = self._find_table_caption(table.page)

            table_data = {
                'page': table.page,
                'content': table.df.to_dict(),
                'accuracy': table.accuracy,
                'caption': caption,
                'rows': table.shape[0],
                'columns': table.shape[1]
            }
            extracted_tables.append(table_data)

        return extracted_tables

    def _extract_references(self, tree: ET.Element) -> List[Dict]:
        """
        Extract and parse references from GROBID XML.

        Returns structured reference data including authors, title,
        publication venue, year, and DOI where available.
        """
        references = []
        for ref in tree.findall('.//listBibl/biblStruct'):
            ref_data = {
                'authors': [],
                'title': ref.findtext('.//title'),
                'journal': ref.findtext('.//journal-title'),
                'year': ref.findtext('.//date/@when'),
                'volume': ref.findtext('.//biblScope[@unit="volume"]'),
                'issue': ref.findtext('.//biblScope[@unit="issue"]'),
                'pages': ref.findtext('.//biblScope[@unit="page"]'),
                'doi': ref.findtext('.//idno[@type="DOI"]')
            }

            # Extract author names
            for author in ref.findall('.//author'):
                author_name = []
                for name_part in author.findall('.//persName//*'):
                    if name_part.text:
                        author_name.append(name_part.text.strip())
                if author_name:
                    ref_data['authors'].append(' '.join(author_name))

            references.append(ref_data)

        return references

    def _save_content(self, content: Dict):
        """Save extracted content to files"""
        paper_id = content['paper_id']

        # Save metadata
        pd.Series(content['metadata']).to_json(
            self.output_dir / f'{paper_id}_metadata.json')

        # Save sections
        pd.DataFrame(content['sections'].items(),
                     columns=['section', 'content']).to_json(
            self.output_dir / f'{paper_id}_sections.json')

        # Save tables
        pd.DataFrame(content['tables']).to_json(
            self.output_dir / f'{paper_id}_tables.json')

        # Save references
        pd.DataFrame(content['references']).to_json(
            self.output_dir / f'{paper_id}_references.json')


if __name__ == "__main__":
    import argparse

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Parse arguments
    parser = argparse.ArgumentParser(description='Process scientific papers using GROBID')
    parser.add_argument('../data/raw/1-s2.0-S1383586624022202-main.pdf', type=Path, required=True,
                        help='Path to PDF file or directory containing PDFs')
    parser.add_argument('../data/processed', type=Path, required=True,
                        help='Output directory for processed content')
    parser.add_argument('--grobid-url', type=str,
                        default='http://localhost:8070',
                        help='URL of GROBID service')

    args = parser.parse_args()

    try:
        # Initialize processor
        processor = ScientificPaperProcessor(
            grobid_url=args.grobid_url,
            output_dir=args.output
        )

        # Process single file or directory
        if args.input.is_file():
            result = processor.process_paper(args.input)
            logging.info(f"Successfully processed {args.input}")
        elif args.input.is_dir():
            for pdf_file in args.input.glob('*.pdf'):
                try:
                    result = processor.process_paper(pdf_file)
                    logging.info(f"Successfully processed {pdf_file}")
                except Exception as e:
                    logging.error(f"Failed to process {pdf_file}: {str(e)}")

    except Exception as e:
        logging.error(f"Processing failed: {str(e)}")