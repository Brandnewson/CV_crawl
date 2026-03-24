"""CV renderer - generates DOCX from template and selections."""

import json
import shutil
import tempfile
import zipfile
from pathlib import Path

from docx import Document
from lxml import etree

from agent.validators import UserSelections


# DOCX XML namespaces
NAMESPACES = {
    'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
    'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
}


def normalise_bullet_text_for_render(text: str) -> str:
    """Trim whitespace and add soft wrap points to very long tokens."""
    cleaned = " ".join((text or "").split())
    if not cleaned:
        return ""

    tokens = cleaned.split(" ")
    wrapped_tokens = []
    for token in tokens:
        if len(token) <= 18:
            wrapped_tokens.append(token)
            continue

        pieces = [token[i:i + 12] for i in range(0, len(token), 12)]
        wrapped_tokens.append("\u200b".join(pieces))

    return " ".join(wrapped_tokens)


def unpack_docx(docx_path: Path, output_dir: Path) -> Path:
    """Unpack DOCX ZIP. Return path to word/document.xml."""
    if not docx_path.exists():
        raise FileNotFoundError(f"DOCX not found: {docx_path}")

    # Clean output directory if it exists
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)

    # DOCX is a ZIP file
    with zipfile.ZipFile(docx_path, 'r') as zf:
        zf.extractall(output_dir)

    doc_xml_path = output_dir / "word" / "document.xml"
    if not doc_xml_path.exists():
        raise FileNotFoundError(f"document.xml not found in DOCX: {docx_path}")

    return doc_xml_path


def repack_docx(unpacked_dir: Path, output_path: Path) -> Path:
    """Repack an unpacked DOCX directory into a DOCX file."""
    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Remove existing output file if present
    if output_path.exists():
        output_path.unlink()

    # Create ZIP with DOCX structure
    # DOCX requires specific file ordering: [Content_Types].xml must be first
    with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        # Add [Content_Types].xml first (required by DOCX spec)
        content_types = unpacked_dir / "[Content_Types].xml"
        if content_types.exists():
            zf.write(content_types, "[Content_Types].xml")

        # Add all other files
        for file_path in unpacked_dir.rglob('*'):
            if file_path.is_file() and file_path.name != "[Content_Types].xml":
                arcname = file_path.relative_to(unpacked_dir)
                zf.write(file_path, arcname)

    return output_path


def load_template_map(map_path: Path) -> dict:
    """Load template map from JSON file."""
    with open(map_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def swap_header_text(header_node: etree._Element, new_text: str) -> None:
    """Replace all non-empty text runs in a header paragraph."""
    for t in header_node.findall('.//w:t', NAMESPACES):
        if t.text and t.text.strip():
            t.text = new_text
            new_text = ""  # only replace first populated run; blank the rest


def swap_bullet_text(bullet_node: etree._Element, new_text: str) -> None:
    """
    Find the <w:r> run containing bullet body text (not the ▪ run).
    Replace <w:t> text with new_text.
    Preserve all <w:rPr> formatting exactly.
    Do not modify the ▪ character run.
    """
    # Bullet characters to skip
    bullet_chars = {'▪', '▫', '●', '•', '◦', '-', '\u25aa', '\u25a0', '\u25ab', '\u25cf', '\u2022'}

    # Find all runs in the paragraph
    runs = bullet_node.findall('.//w:r', NAMESPACES)

    # Find the first run that contains actual text (not just bullet char)
    text_runs = []
    for run in runs:
        t_elements = run.findall('.//w:t', NAMESPACES)
        for t in t_elements:
            if t.text and t.text.strip() and t.text.strip() not in bullet_chars:
                text_runs.append((run, t))

    if not text_runs:
        # No text runs found - might be an empty bullet, create text in first run
        if runs:
            first_run = runs[0]
            t_element = first_run.find('.//w:t', NAMESPACES)
            if t_element is None:
                # Create new t element
                t_element = etree.SubElement(first_run, '{%s}t' % NAMESPACES['w'])
                t_element.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
            t_element.text = new_text
        return

    # Clear all text runs except first, which we'll use for new text
    first_run, first_t = text_runs[0]
    first_t.text = new_text

    # Clear subsequent text runs (but keep runs for formatting)
    for run, t in text_runs[1:]:
        t.text = ""


def clear_paragraph_text(para_node: etree._Element) -> None:
    """Clear all text in a paragraph (for hiding projects)."""
    for t_element in para_node.findall('.//w:t', NAMESPACES):
        t_element.text = ""


def remove_numpr(para_node: etree._Element) -> None:
    """Remove numPr element to suppress list formatting."""
    for ppr in para_node.findall('.//w:pPr', NAMESPACES):
        for numpr in ppr.findall('.//w:numPr', NAMESPACES):
            ppr.remove(numpr)


def render_cv(
    template_path: Path,
    template_map_path: Path,
    selections: UserSelections,
    job: dict,
    output_path: Path,
    insert_page_break_before_technical_projects: bool = True,
) -> Path:
    """
    1. Copy template to output_path (never touch original)
    2. Unpack copy
    3. Parse document.xml with lxml
    4. For each approved_bullet in selections:
       - Find bullet node by XPath from template_map
       - Call swap_bullet_text()
    5. For each hidden project:
       - Set title_stack text to ""
       - Set all bullet texts to ""
       - Remove numPr from bullet nodes (suppress list formatting)
    6. Repack to output_path
    7. Validate: open with python-docx, check no error
    8. Return output_path
    """
    # Validate inputs
    if not template_path.exists():
        raise FileNotFoundError(f"Template not found: {template_path}")
    if not template_map_path.exists():
        raise FileNotFoundError(f"Template map not found: {template_map_path}")

    # Load template map
    template_map = load_template_map(template_map_path)

    # Create temp directory for unpacking
    temp_dir = Path(tempfile.mkdtemp(prefix="cv_render_"))

    try:
        # Step 1: Copy template to temp location
        temp_docx = temp_dir / "template_copy.docx"
        shutil.copy2(template_path, temp_docx)

        # Step 2: Unpack the copy
        unpacked_dir = temp_dir / "unpacked"
        doc_xml_path = unpack_docx(temp_docx, unpacked_dir)

        # Step 3: Parse document.xml with lxml
        tree = etree.parse(str(doc_xml_path))
        root = tree.getroot()

        # Step 4: For each approved bullet, find node and swap text
        for bullet in selections.approved_bullets:
            section = bullet['section']
            subsection = bullet['subsection']
            slot_index = bullet['slot_index']
            new_text = normalise_bullet_text_for_render(bullet['text'])

            # Get bullet xpaths for this subsection
            if section in template_map and subsection in template_map[section]:
                bullet_xpaths = template_map[section][subsection].get('bullet_xpaths', [])

                if 0 <= slot_index < len(bullet_xpaths):
                    xpath = bullet_xpaths[slot_index]

                    # Find the node
                    try:
                        nodes = root.xpath(xpath, namespaces=NAMESPACES)
                        if nodes:
                            swap_bullet_text(nodes[0], new_text)
                    except Exception:
                        pass

        # Step 4b: Apply header swaps (rename project titles)
        for swap in getattr(selections, 'header_swaps', []):
            section = swap.get('section')
            subsection = swap.get('subsection')
            idx = swap.get('header_xpath_index', 0)
            new_text = swap.get('text', '')
            if section in template_map and subsection in template_map[section]:
                header_xpaths = template_map[section][subsection].get('header_xpaths', [])
                if 0 <= idx < len(header_xpaths):
                    try:
                        nodes = root.xpath(header_xpaths[idx], namespaces=NAMESPACES)
                        if nodes:
                            swap_header_text(nodes[0], new_text)
                    except Exception:
                        pass

        # Step 5: For each hidden project, clear content
        for project_name in selections.hidden_projects:
            # Check both sections for hidden projects
            for section in ['work_experience', 'technical_projects']:
                if section in template_map and project_name in template_map[section]:
                    subsection_data = template_map[section][project_name]

                    # Clear header xpaths (title, dates, etc.)
                    for xpath in subsection_data.get('header_xpaths', []):
                        try:
                            nodes = root.xpath(xpath, namespaces=NAMESPACES)
                            if nodes:
                                clear_paragraph_text(nodes[0])
                        except Exception:
                            pass

                    # Clear bullet xpaths and remove list formatting
                    for xpath in subsection_data.get('bullet_xpaths', []):
                        try:
                            nodes = root.xpath(xpath, namespaces=NAMESPACES)
                            if nodes:
                                clear_paragraph_text(nodes[0])
                                remove_numpr(nodes[0])
                        except Exception:
                            pass

        if insert_page_break_before_technical_projects:
            # Insert page break before the Technical Projects section heading (p[47]).
            try:
                page_break_para = root.xpath('/w:document/w:body/w:p[47]', namespaces=NAMESPACES)
                if page_break_para:
                    para = page_break_para[0]
                    w_ns = NAMESPACES['w']
                    run_el = etree.Element('{%s}r' % w_ns)
                    br_el = etree.SubElement(run_el, '{%s}br' % w_ns)
                    br_el.set('{%s}type' % w_ns, 'page')
                    ppr = para.find('{%s}pPr' % w_ns)
                    insert_pos = (list(para).index(ppr) + 1) if ppr is not None else 0
                    para.insert(insert_pos, run_el)
            except Exception:
                pass

        # Write modified XML back
        tree.write(
            str(doc_xml_path),
            encoding='UTF-8',
            xml_declaration=True,
            standalone=True
        )

        # Step 6: Repack to output_path
        repack_docx(unpacked_dir, output_path)

        # Step 7: Validate - open with python-docx to check no corruption
        try:
            doc = Document(output_path)
            _ = len(doc.paragraphs)
        except Exception as e:
            raise ValueError(f"Generated DOCX is corrupted: {e}")

        # Step 8: Return output_path
        return output_path

    finally:
        # Clean up temp directory
        if temp_dir.exists():
            shutil.rmtree(temp_dir)


