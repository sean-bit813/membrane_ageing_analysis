import logging
import re
from typing import Dict, List

import fitz


class SectionProcessor:
    def __init__(self):
        # Define section order for validation
        self.section_order = [
            'introduction',
            'methods',
            'results',
            'discussion',
            'conclusions',
            'references'
        ]

    def extract_sections(self, doc: fitz.Document) -> Dict[str, str]:
        """
        Extract sections from two-column scientific paper with structured format.

        Parameters:
            doc (fitz.Document): Input PDF document

        Returns:
            Dict[str, str]: Extracted sections with standardized keys
        """

        logging.info("Starting section extraction")

        # Define section patterns with strict boundaries
        section_patterns = {
            'introduction': r'(?:^|\n)(?:1\.?\s*)?(?i:introduction|intro)\s*$',
            'experimental': r'(?:^|\n)(?:2\.?\s*)?(?i:(?:materials?\s+and\s+methods?|methods?\s+and\s+materials?|experimental\s+section?|methodology|experimental|methods?|materials?))\s*$',
            'results': r'(?:^|\n)(?:3\.?\s*)?(?i:results?(?:\s+and\s+discussion)?|findings)\s*$',
            'discussion': r'(?:^|\n)(?:4\.?\s*)?(?i:discussion|discussion\s+of\s+results?)\s*$',
            'conclusions': r'(?:^|\n)(?:5\.?\s*)?(?i:conclusions?|concluding\s+remarks?|summary)\s*$',
            'references': r'(?:^|\n)(?i:references?|literature\s+cited|bibliography)\s*$'
        }

        # Process each page preserving text flow
        text_blocks = []
        for page_num, page in enumerate(doc):
            # Get page blocks with position info
            blocks = page.get_text("dict")["blocks"]

            # Sort blocks by column and vertical position
            text_blocks.extend(self._process_column_blocks(blocks, page_num))

        # Reconstruct full text maintaining document flow
        full_text = self._reconstruct_document_text(text_blocks)

        # Extract sections with validation
        sections = {}
        section_positions = self._find_section_positions(full_text, section_patterns)

        for i, section in enumerate(section_positions):
            start_pos = section['start']
            end_pos = section_positions[i + 1]['start'] if i < len(section_positions) - 1 else len(full_text)

            content = full_text[start_pos:end_pos].strip()

            # Validate section content
            if self._validate_section_content(section['name'], content):
                sections[section['name']] = content

        return sections

    def _reconstruct_document_text(self, blocks: List[Dict]) -> str:
        """Reconstruct document text maintaining logical flow"""
        blocks.sort(key=lambda b: (b['page'], b['bbox'][1]))
        return "\n".join(block['text'] for block in blocks)


    def _process_column_blocks(self, blocks: List[Dict], page_num: int) -> List[Dict]:
        """Process text blocks accounting for two-column layout"""
        processed_blocks = []

        # Sort blocks by column (x position) then vertical position
        blocks.sort(key=lambda b: (b['bbox'][0], b['bbox'][1]))

        # Group blocks by column
        column_width = 300  # Approximate width threshold for columns
        current_column = []
        current_x = 0

        for block in blocks:
            if 'lines' in block:
                # Check if block starts new column
                if abs(block['bbox'][0] - current_x) > column_width:
                    # Process previous column
                    if current_column:
                        processed_blocks.extend(current_column)
                    current_column = []
                    current_x = block['bbox'][0]

                text = ' '.join(span['text'] for line in block['lines']
                                for span in line['spans'])

                if text.strip():
                    current_column.append({
                        'text': text,
                        'bbox': block['bbox'],
                        'page': page_num
                    })

        # Add final column
        if current_column:
            processed_blocks.extend(current_column)

        return processed_blocks


    def _validate_section_content(self, section_name: str, content: str) -> bool:
        """Validate section content matches expected patterns"""
        if not content or len(content) < 100:  # Minimum content length
            return False

        # Section-specific validation
        if section_name == 'introduction':
            if not any(x in content.lower() for x in ['background', 'study', 'aim']):
                return False

        elif section_name == 'methods':
            if not any(x in content.lower() for x in ['experiment', 'analysis', 'protocol']):
                return False

        elif section_name == 'results':
            if not any(x in content.lower() for x in ['fig', 'table', 'observed']):
                return False

        elif section_name == 'references':
            if not re.search(r'\[\d+\]|\(\d{4}\)', content):
                return False

        return True

    def _extract_text_blocks(self, doc: fitz.Document) -> List[Dict]:
        """Extract text blocks with spatial information"""
        text_blocks = []
        for page_num, page in enumerate(doc):
            blocks = page.get_text("dict")["blocks"]
            for block in blocks:
                if "lines" in block:
                    text = self._process_block_text(block)
                    if text.strip():
                        text_blocks.append({
                            'text': text.strip(),
                            'bbox': block['bbox'],
                            'page': page_num
                        })
        return text_blocks

    def _process_block_text(self, block: Dict) -> str:
        """Process text from block while preserving structure"""
        text = ""
        for line in block["lines"]:
            line_text = " ".join(span["text"] for span in line["spans"])
            text += line_text + " "
        return text

    def _identify_sections(self, text: str) -> Dict[str, str]:
        """Identify and validate document sections"""
        sections = {}
        section_positions = self._find_section_positions(text)

        if not section_positions:
            return {}

        for i, section in enumerate(section_positions):
            start = section['start']
            end = (section_positions[i + 1]['pattern_start']
                   if i < len(section_positions) - 1 else len(text))
            content = text[start:end].strip()

            #if self._validate_section(section['name'], content):
                #sections[section['name']] = content

        return sections

    def _find_section_positions(self, text: str, section_patterns) -> List[Dict]:
        """Locate section boundaries in text"""
        positions = []
        for name, pattern in section_patterns.items():
            for match in re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE):
                positions.append({
                    'name': name,
                    'start': match.end(),
                    'pattern_start': match.start()
                })
        return sorted(positions, key=lambda x: x['pattern_start'])
