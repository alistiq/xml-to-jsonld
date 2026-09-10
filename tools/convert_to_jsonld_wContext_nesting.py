#!/usr/bin/env python3
"""
Convert RDF/XML files to JSON-LD format with hierarchical blank node nesting
and original XML property ordering.
Usage: python convert_to_jsonld.py input.rdf output.jsonld
"""
import json
import sys
import xml.etree.ElementTree as ET

from rdflib import Graph
from rdflib.namespace import RDF


XSD_URI = "http://www.w3.org/2001/XMLSchema#"
RDF_URI  = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"


# ── Namespace helpers ────────────────────────────────────────────────────────

def get_xml_namespaces(input_file):
    """Extract namespace declarations from the raw XML, preserving original
    prefix names as declared in the source file."""
    namespaces = {}
    for _, (prefix, uri) in ET.iterparse(input_file, events=["start-ns"]):
        if prefix:
            namespaces[prefix] = uri
    return namespaces


def build_context(xml_namespaces, g, used_prefixes):
    """Build the JSON-LD @context from used XML prefixes.

    - Always injects xsd (for typed-literal shortening).
    - Drops the rdf prefix when no non-rdf:type RDF predicates are present,
      because rdf:type is always serialised as @type in JSON-LD.
    """
    rdf_non_type_used = any(
        str(p).startswith(RDF_URI) and p != RDF.type
        for _, p, _ in g
    )
    context = {}
    for prefix, uri in xml_namespaces.items():
        if prefix not in used_prefixes:
            continue
        if uri == RDF_URI and not rdf_non_type_used:
            continue
        context[prefix] = uri
    context["xsd"] = XSD_URI
    return context


# ── XML predicate-order extraction ──────────────────────────────────────────

def _clark_uri(tag):
    """Convert ElementTree Clark notation {uri}local → uri+local."""
    if tag.startswith("{"):
        ns, local = tag[1:].split("}", 1)
        return ns + local
    return tag


def get_xml_property_order(input_file):
    """Parse the RDF/XML source and record the order of predicates per node
    type, exactly as they appear in the file.

    Returns: dict  type_full_uri -> [predicate_full_uri, ...]
    The first time a type is encountered wins (handles repeated types).
    """
    RDF_DESC = RDF_URI + "Description"
    RDF_TYPE = RDF_URI + "type"
    type_order = {}

    def process_subject(elem):
        elem_uri = _clark_uri(elem.tag)

        # Determine the subject's rdf:type
        if elem_uri == RDF_DESC:
            # Explicit rdf:type attribute on rdf:Description
            type_uri = elem.get("{%s}type" % RDF_URI)
            # … or as a child rdf:type element
            if not type_uri:
                for child in elem:
                    if _clark_uri(child.tag) == RDF_TYPE:
                        type_uri = child.get("{%s}resource" % RDF_URI)
                        break
        else:
            type_uri = elem_uri  # the element tag IS the type

        if type_uri and type_uri not in type_order:
            predicates = []
            for child in elem:
                pred_uri = _clark_uri(child.tag)
                if pred_uri != RDF_TYPE and pred_uri not in predicates:
                    predicates.append(pred_uri)
            if predicates:
                type_order[type_uri] = predicates

        # Recurse into inline blank-node subjects (nested inside property elements)
        for child in elem:
            for grandchild in child:
                process_subject(grandchild)

    tree = ET.parse(input_file)
    root = tree.getroot()

    top_subjects = (
        list(root)                  # children of rdf:RDF wrapper
        if _clark_uri(root.tag) == RDF_URI + "RDF"
        else [root]
    )
    for elem in top_subjects:
        process_subject(elem)

    return type_order


# ── CURIE expansion & key ordering ──────────────────────────────────────────

def _expand_curie(curie, context):
    """Expand a prefixed name like 'pper:givenName' to its full URI."""
    if (isinstance(curie, str)
            and ":" in curie
            and not curie.startswith("@")
            and not curie.startswith("http")):
        prefix, local = curie.split(":", 1)
        if prefix in context and isinstance(context[prefix], str):
            return context[prefix] + local
    return curie


def apply_ordering(obj, type_order, context):
    """Recursively sort each node's predicate keys to match the XML source
    order for that node's rdf:type."""
    if isinstance(obj, dict):
        # Literal value objects ({"@value": ..., "@type"/"@language": ...})
        # are already in the correct order from resolve(); leave them alone.
        if "@value" in obj:
            return obj

        if "@type" in obj and isinstance(obj["@type"], str):
            type_uri = _expand_curie(obj["@type"], context)
            order    = type_order.get(type_uri, [])

            def key_pos(key):
                if key.startswith("@"):
                    # @-keywords always first; @type before everything else
                    return (-1, {"@type": 0, "@id": 1}.get(key, 2), key)
                full_uri = _expand_curie(key, context)
                try:
                    return (order.index(full_uri), 0, key)
                except ValueError:
                    return (len(order), 0, key)   # unknown predicates at end

            obj = dict(sorted(obj.items(), key=lambda kv: key_pos(kv[0])))

        return {k: apply_ordering(v, type_order, context) for k, v in obj.items()}

    elif isinstance(obj, list):
        return [apply_ordering(item, type_order, context) for item in obj]

    return obj


# ── Blank-node nesting ───────────────────────────────────────────────────────

def _collect_bnode_refs(val, result_set):
    """Walk a value tree and collect every blank-node @id referenced in it."""
    if isinstance(val, dict):
        if len(val) == 1 and "@id" in val and str(val["@id"]).startswith("_:"):
            result_set.add(val["@id"])
        else:
            for v in val.values():
                _collect_bnode_refs(v, result_set)
    elif isinstance(val, list):
        for item in val:
            _collect_bnode_refs(item, result_set)


def _shorten_xsd(type_val):
    """Replace a full XSD URI with the xsd: prefixed form."""
    if isinstance(type_val, str) and type_val.startswith(XSD_URI):
        return "xsd:" + type_val[len(XSD_URI):]
    return type_val


def nest_jsonld_graph(parsed_json):
    """Transform a flat @graph JSON-LD into a hierarchical nested structure.

    Rules applied:
      1. Blank nodes are inlined recursively wherever they are referenced.
      2. Named nodes (real IRIs) remain as separate @graph entries.
      3. Root blank node(s) appear first in @graph without an @id.
      4. Plain string literals become {"@value": "...", "@type": "xsd:string"}.
      5. Full XSD type URIs are shortened to xsd:<localname>.
      6. Literal value objects are normalised to {@value, @type/@language} order.
    """
    if "@graph" not in parsed_json:
        return parsed_json

    graph = parsed_json["@graph"]

    # Separate blank nodes from named (IRI) nodes
    blank_node_map = {}
    named_nodes    = []

    for node in graph:
        node_id = node.get("@id", "")
        if str(node_id).startswith("_:"):
            blank_node_map[node_id] = node
        else:
            named_nodes.append(node)

    # Root blank nodes = those never referenced by another node
    referenced_bnode_ids = set()
    for node in graph:
        for key, val in node.items():
            if key != "@id":
                _collect_bnode_refs(val, referenced_bnode_ids)

    root_bnode_ids = [
        nid for nid in blank_node_map
        if nid not in referenced_bnode_ids
    ]

    def resolve(element, visiting=None):
        """Inline blank-node references and normalise literals."""
        if visiting is None:
            visiting = set()

        if isinstance(element, dict):

            # Blank-node reference: {"@id": "_:N..."}
            if (len(element) == 1
                    and "@id" in element
                    and str(element["@id"]).startswith("_:")):
                bnode_id = element["@id"]
                if bnode_id in blank_node_map and bnode_id not in visiting:
                    target = dict(blank_node_map[bnode_id])
                    target.pop("@id", None)
                    return resolve(target, visiting | {bnode_id})
                return element   # unknown bnode or cycle guard

            # Literal value object – normalise to {@value, @type/@language}
            if "@value" in element:
                result = {"@value": element["@value"]}
                if "@type" in element:
                    result["@type"] = _shorten_xsd(element["@type"])
                if "@language" in element:
                    result["@language"] = element["@language"]
                return result

            # Regular node – pass @-keywords through unchanged, recurse into rest
            result = {}
            for k, v in element.items():
                if k in ("@id", "@type", "@language", "@value"):
                    result[k] = v
                else:
                    result[k] = resolve(v, visiting)
            return result

        elif isinstance(element, list):
            return [resolve(item, visiting) for item in element]

        elif isinstance(element, str):
            # Plain string literal → explicit xsd:string
            return {"@value": element, "@type": "xsd:string"}

        return element

    # Build the new @graph
    new_graph = []

    for root_id in root_bnode_ids:
        root_node = dict(blank_node_map[root_id])
        root_node.pop("@id", None)
        new_graph.append(resolve(root_node, {root_id}))

    for node in named_nodes:
        new_graph.append(resolve(node))

    return {
        "@context": parsed_json.get("@context", {}),
        "@graph": new_graph,
    }


# ── Main conversion ──────────────────────────────────────────────────────────

def convert_rdfxml_to_jsonld(input_file, output_file):
    """Convert RDF/XML to nested, correctly-ordered JSON-LD."""
    try:
        print(f"Reading namespace declarations from: {input_file}")
        xml_namespaces = get_xml_namespaces(input_file)

        g = Graph()
        print(f"Parsing RDF/XML from: {input_file}")
        g.parse(input_file, format="xml")

        # Filter context to only prefixes actually used in triples
        used_prefixes = set()
        for subject, predicate, obj in g:
            for term in (subject, predicate, obj):
                term_str = str(term)
                for prefix, uri in xml_namespaces.items():
                    if term_str.startswith(uri):
                        used_prefixes.add(prefix)

        context = build_context(xml_namespaces, g, used_prefixes)

        print("Extracting predicate order from XML source...")
        type_order = get_xml_property_order(input_file)

        print("Serialising to flat JSON-LD...")
        raw_jsonld = g.serialize(format="json-ld", indent=2, context=context)

        print("Nesting blank nodes into hierarchical tree...")
        flat   = json.loads(raw_jsonld)
        nested = nest_jsonld_graph(flat)

        print("Applying original XML predicate ordering...")
        nested = apply_ordering(nested, type_order, context)

        print(f"Writing JSON-LD to: {output_file}")
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(nested, f, indent=2, ensure_ascii=False)

        print("✓ Conversion successful!")

    except Exception as e:
        print(f"✗ Error during conversion: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python convert_to_jsonld.py input.rdf output.jsonld")
        sys.exit(1)

    convert_rdfxml_to_jsonld(sys.argv[1], sys.argv[2])