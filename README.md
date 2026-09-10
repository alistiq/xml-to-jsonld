# xml-to-jsonld

A worked, runnable example of transforming a Slovak e-gov XML registry record
into RDF/XML and JSON-LD, using the shared `data.gov.sk` CMU ontology (`pper:`
physical person, `loca:` location, plus ADMS and SKOS).

## Structure

`Example/` holds a self-contained, synthetic (fictional registry, not derived
from any real government schema) worked example of the full pipeline —
see below.

`tools/` holds the two scripts that run that pipeline.

All sample data (names, birth numbers, addresses, IDs) in this repository is
synthetic/placeholder data and does not represent real individuals.

## Example pipeline

The XML instance and its XSD schemas are the **inputs**. The XSLT stylesheet
is a **hand-authored mapping** from that XML shape to the CMU ontology — it
doesn't come out of the XML/XSD, someone has to write it. The two scripts are
what actually **execute** the pipeline, producing the RDF/XML and JSON-LD
outputs:

```
  example.xml  ─┐
                 ├─validated by──  example.xsd + referencing.xsd
                 │
                 ▼
  example.xslt (hand-authored mapping to pper:/loca:)
                 │
                 ▼  [run via run_xslt.py]
  example.rdf
                 │
                 ▼  [run via convert_to_jsonld_wContext_nesting.py]
  example.jsonld
```

`Example/` contains every artifact for a single synthetic "person + address"
query-by-identifier record:

| File | Role | Purpose |
|---|---|---|
| `Example/example.xml` | Input | A sample XML instance conforming to `example.xsd` |
| `Example/example.xsd` | Input | The source XSD schema (fictional registry, structurally typical of a Slovak e-gov query-by-identifier web service) |
| `Example/referencing.xsd` | Input | Shared `tmid:` codelist-reference schema (MetaIS-resolved codelist items) imported by `example.xsd` |
| `Example/example.xslt` | Mapping | XSLT 3.0 stylesheet, hand-written to map the XML to RDF/XML using the CMU `pper:`/`loca:` ontology, verified against the live `slovak-egov/centralny-model-udajov` ontologies |
| `Example/example.rdf` | Pipeline output | The RDF/XML produced by running `example.xslt` over `example.xml` |
| `Example/example.jsonld` | Pipeline output | The final JSON-LD, produced by converting `example.rdf` |

Reproduce it:

```bash
uv run tools/run_xslt.py Example/example.xslt Example/example.xml Example/example.rdf
uv run --with rdflib tools/convert_to_jsonld_wContext_nesting.py Example/example.rdf Example/example.jsonld
```

- **`tools/run_xslt.py`** — runs an XSLT 3.0 stylesheet over an XML file using
  Saxon-HE (`saxonche`), producing RDF/XML.
- **`tools/convert_to_jsonld_wContext_nesting.py`** — converts that RDF/XML
  into JSON-LD, nesting blank nodes into a hierarchical tree and preserving
  the original XML element order for each type (using `rdflib`).

## License

MIT — see [LICENSE](LICENSE).
