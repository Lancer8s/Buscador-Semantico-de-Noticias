"""
Sistema de Búsqueda de Noticias con Ontología Semántica.
Integra búsqueda local (RDF) y online (DBpedia) con soporte multilingüe.
"""

import os
from flask import Flask, request, render_template, jsonify
from rdflib import Graph, Namespace, Literal, URIRef
from rdflib.namespace import RDF, RDFS, OWL, XSD
from SPARQLWrapper import SPARQLWrapper, JSON
from googletrans import Translator
import urllib.parse

from dbpedia_manager import initialize_dbpedia, HybridSearchEngine


class NewsSearchConfig:
    """Configuración centralizada de la aplicación."""
    
    LANGUAGES = {
        'es': 'Español',
        'en': 'English',
        'pt': 'Português'
    }
    
    ONTOLOGY_NS = Namespace("http://www.semanticweb.org/cabez/ontologies/2025/2/untitled-ontology-3#")
    DBPEDIA_ENDPOINT = "http://dbpedia.org/sparql"
    
    TRANSLATIONS = {
        'search_placeholder': {
            'es': 'Buscar noticias...',
            'en': 'Search news...',
            'pt': 'Pesquisar notícias...'
        },
        'search_button': {
            'es': 'Buscar',
            'en': 'Search',
            'pt': 'Pesquisar'
        },
        'title': {
            'es': 'Buscador de Noticias',
            'en': 'News Search',
            'pt': 'Pesquisa de Notícias'
        },
        'no_results': {
            'es': 'No se encontraron noticias para',
            'en': 'No news found for',
            'pt': 'Nenhuma notícia encontrada para'
        },
        'results_for': {
            'es': 'Resultados para',
            'en': 'Results for',
            'pt': 'Resultados para'
        },
        'date': {
            'es': 'Fecha',
            'en': 'Date',
            'pt': 'Data'
        },
        'topic': {
            'es': 'Tema',
            'en': 'Topic',
            'pt': 'Tema'
        },
        'author': {
            'es': 'Autor',
            'en': 'Author',
            'pt': 'Autor'
        },
        'verification': {
            'es': 'Verificación',
            'en': 'Verification',
            'pt': 'Verificação'
        },
        'not_verified': {
            'es': 'No verificada',
            'en': 'Not verified',
            'pt': 'Não verificada'
        },
        'view_details': {
            'es': 'Ver detalles',
            'en': 'View details',
            'pt': 'Ver detalhes'
        },
        'view_on_dbpedia': {
            'es': 'Ver en DBpedia',
            'en': 'View on DBpedia',
            'pt': 'Ver no DBpedia'
        },
        'local_results': {
            'es': 'Resultados Locales',
            'en': 'Local Results',
            'pt': 'Resultados Locais'
        },
        'dbpedia_results': {
            'es': 'Resultados de DBpedia',
            'en': 'DBpedia Results',
            'pt': 'Resultados do DBpedia'
        },
        'inferred_results': {
            'es': 'Resultados Inferidos',
            'en': 'Inferred Results',
            'pt': 'Resultados Inferidos'
        },
        'back': {
            'es': 'Volver',
            'en': 'Back',
            'pt': 'Voltar'
        },
        'news_details': {
            'es': 'Detalle de la Noticia',
            'en': 'News Details',
            'pt': 'Detalhes da Notícia'
        },
        'dark_mode': {
            'es': 'Modo Oscuro',
            'en': 'Dark Mode',
            'pt': 'Modo Escuro'
        },
        'light_mode': {
            'es': 'Modo Claro',
            'en': 'Light Mode',
            'pt': 'Modo Claro'
        },
        'translated_from': {
            'es': 'Traducido del',
            'en': 'Translated from',
            'pt': 'Traduzido do'
        },
        'no_dbpedida_results': {
            'es': 'No se encontraron resultados en DBpedia',
            'en': 'No results found in DBpedia',
            'pt': 'Nenhum resultado encontrado no DBpedia'
        }
    }


class RDFSearchEngine:
    """Motor de búsqueda para la ontología RDF local."""
    
    def __init__(self, graph: Graph, ontology_ns: Namespace):
        self.graph = graph
        self.ontology_ns = ontology_ns
    
    def build_query(self, keyword: str, search_type: str = "general") -> str:
        filters = self._build_filters(keyword, search_type)
        filter_clause = f"FILTER ({' || '.join(filters)})" if filters else ""
        
        return f"""
            PREFIX untitled-ontology-3: <http://www.semanticweb.org/cabez/ontologies/2025/2/untitled-ontology-3#>
            PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            
            SELECT DISTINCT ?noticia ?titulo ?fecha ?tematica ?autor ?estadoVerificacion
            WHERE {{
                ?noticia rdf:type ?tipoNoticia .
                ?tipoNoticia rdfs:subClassOf* untitled-ontology-3:Noticia .
                
                OPTIONAL {{ ?noticia untitled-ontology-3:Título ?titulo . }}
                OPTIONAL {{ ?noticia untitled-ontology-3:Fecha_publicación ?fecha . }}
                OPTIONAL {{ ?noticia untitled-ontology-3:Temática ?tematica . }}
                OPTIONAL {{ ?noticia untitled-ontology-3:Autor ?autor . }}
                
                {filter_clause}
                
                OPTIONAL {{
                    ?verificacion untitled-ontology-3:evalua ?noticia ;
                                  untitled-ontology-3:Estado ?estadoVerificacion .
                }}
            }}
            ORDER BY DESC(?fecha)
        """
    
    def _build_filters(self, keyword: str, search_type: str) -> list:
        keyword_escaped = keyword.replace('"', '\\"')
        
        filter_map = {
            "general": [
                f'CONTAINS(LCASE(STR(?titulo)), LCASE("{keyword_escaped}"))',
                f'CONTAINS(LCASE(STR(?tematica)), LCASE("{keyword_escaped}"))',
                f'CONTAINS(LCASE(STR(?autor)), LCASE("{keyword_escaped}"))'
            ],
            "autor": [f'CONTAINS(LCASE(STR(?autor)), LCASE("{keyword_escaped}"))'],
            "tema": [f'CONTAINS(LCASE(STR(?tematica)), LCASE("{keyword_escaped}"))'],
            "fecha": [f'STR(?fecha) = "{keyword_escaped}"'],
            "verificadas": ['?estadoVerificacion = untitled-ontology-3:Verificada']
        }
        
        return filter_map.get(search_type, filter_map["general"])
    
    def execute_search(self, query: str) -> list:
        try:
            results = list(self.graph.query(query))
            return [
                {
                    "uri": str(row.noticia),
                    "titulo": str(row.titulo) if row.titulo else "Sin título",
                    "fecha": self._format_date(row.fecha) if row.fecha else "?",
                    "tematica": str(row.tematica) if row.tematica else "?",
                    "autor": str(row.autor) if row.autor else "?",
                    "verificacion": str(row.estadoVerificacion) if row.estadoVerificacion else "No verificada",
                    "original_lang": "es"
                }
                for row in results
            ]
        except Exception as e:
            print(f"Error en consulta SPARQL: {e}")
            return []
    
    @staticmethod
    def _format_date(fecha) -> str:
        try:
            return fecha.toPython().strftime("%Y-%m-%d") if hasattr(fecha, 'toPython') else str(fecha)
        except:
            return str(fecha)


class OnlineSearchEngine:
    """Motor de búsqueda online para DBpedia."""
    
    def __init__(self, endpoint: str = "http://dbpedia.org/sparql"):
        self.endpoint = endpoint
        self.sparql = SPARQLWrapper(endpoint)
        self.sparql.setReturnFormat(JSON)
    
    def query_dbpedia(self, search_term: str, lang: str = 'en') -> list:
        query = f"""
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX dbo: <http://dbpedia.org/ontology/>
            
            SELECT DISTINCT ?resource ?label ?abstract WHERE {{
                ?resource rdfs:label ?label .
                FILTER(LANG(?label) = "{lang}")
                FILTER(CONTAINS(LCASE(STR(?label)), LCASE("{search_term}")))
                
                OPTIONAL {{ 
                    ?resource dbo:abstract ?abstract .
                    FILTER(LANG(?abstract) = "{lang}") 
                }}
                
                FILTER(STRSTARTS(STR(?resource), "http://dbpedia.org/resource/"))
            }}
            LIMIT 5
        """
        
        try:
            self.sparql.setQuery(query)
            results = self.sparql.query().convert()
            
            return [
                {
                    "resource": {"value": binding["resource"]["value"]},
                    "label": {"value": binding["label"]["value"]},
                    "abstract": {"value": binding.get("abstract", {}).get("value", "")}
                }
                for binding in results["results"]["bindings"]
            ]
        except Exception as e:
            print(f"⚠️  Búsqueda online no disponible: {e}")
            return []


class SearchManager:
    """Gestor centralizado de búsquedas offline y online."""
    
    def __init__(self, rdf_engine: RDFSearchEngine, online_engine: OnlineSearchEngine, 
                 dbpedia_index):
        self.rdf_engine = rdf_engine
        self.online_engine = online_engine
        self.dbpedia_index = dbpedia_index
    
    def search_news(self, keyword: str, lang: str = 'es') -> tuple:
        query_type = self._detect_search_type(keyword)
        query = self.rdf_engine.build_query(keyword, query_type)
        local_results = self.rdf_engine.execute_search(query)
        
        for result in local_results:
            result["titulo"] = self._translate_if_needed(result["titulo"], lang)
            result["tematica"] = self._translate_if_needed(result["tematica"], lang)
            result["autor"] = self._translate_if_needed(result["autor"], lang)
        
        return local_results, query_type
    
    def search_dbpedia(self, keyword: str, lang: str = 'es', use_online: bool = True) -> list:
        local_results = self.dbpedia_index.search(keyword)
        
        if use_online and len(local_results) == 0:
            try:
                lang_code = 'en' if lang == 'en' else 'es' if lang == 'es' else 'pt'
                online_results = self.online_engine.query_dbpedia(keyword, lang_code)
                if online_results:
                    local_results.extend(online_results)
            except Exception as e:
                print(f"⚠️  No se pudo buscar en DBpedia online: {e}")
        
        return local_results
    
    @staticmethod
    def _detect_search_type(keyword: str) -> str:
        keyword_lower = keyword.lower()
        
        if "autor:" in keyword_lower or "author:" in keyword_lower:
            return "autor"
        elif "tema:" in keyword_lower or "topic:" in keyword_lower:
            return "tema"
        elif "fecha:" in keyword_lower or "date:" in keyword_lower:
            return "fecha"
        elif "verificadas" in keyword_lower or "verified" in keyword_lower:
            return "verificadas"
        
        return "general"
    
    @staticmethod
    def _translate_if_needed(text: str, target_lang: str) -> str:
        if target_lang == 'es' or not text or text == '?':
            return text
        
        try:
            translator = Translator()
            translation = translator.translate(text, src='es', dest=target_lang)
            return translation.text
        except:
            return text


def load_ontology() -> Graph:
    graph = Graph()
    try:
        if os.path.exists("noticias_ontologia.rdf"):
            graph.parse("noticias_ontologia.rdf", format="xml")
        elif os.path.exists("noticias_ontologia.owl"):
            graph.parse("noticias_ontologia.owl", format="xml")
        print(f"✓ Ontología cargada: {len(graph)} tripletas")
    except Exception as e:
        print(f"✗ Error cargando ontología: {e}")
    
    return graph


def infer_properties(graph: Graph, subject: URIRef) -> dict:
    classes = set()
    
    for s, p, o in graph.triples((subject, RDF.type, None)):
        classes.add(o)
        for s2, p2, o2 in graph.triples((o, RDFS.subClassOf, None)):
            classes.add(o2)
    
    properties = set()
    for class_uri in classes:
        for s, p, o in graph.triples((class_uri, RDFS.domain, None)):
            properties.add(p)
    
    return {
        'classes': [str(c) for c in classes],
        'possible_properties': [str(p) for p in properties]
    }


app = Flask(__name__)

graph = load_ontology()
rdf_engine = RDFSearchEngine(graph, NewsSearchConfig.ONTOLOGY_NS)
online_engine = OnlineSearchEngine(NewsSearchConfig.DBPEDIA_ENDPOINT)
dbpedia_index = initialize_dbpedia()
search_manager = SearchManager(rdf_engine, online_engine, dbpedia_index)


@app.route("/", methods=["GET", "POST"])
def search():
    lang = request.args.get('lang', 'es')
    dark_mode = request.cookies.get('dark_mode', 'true') == 'true'
    keyword = request.args.get('keyword', '') or request.form.get("keyword", "")
    
    local_results = []
    dbpedia_results = []
    
    if keyword:
        local_results, _ = search_manager.search_news(keyword, lang)
        
        if len(local_results) < 5:
            dbpedia_results = search_manager.search_dbpedia(keyword, lang, use_online=False)
    
    return render_template(
        "search.html",
        local_results=local_results,
        dbpedia_results=dbpedia_results,
        keyword=keyword,
        languages=NewsSearchConfig.LANGUAGES,
        current_lang=lang,
        translations=NewsSearchConfig.TRANSLATIONS,
        dark_mode=dark_mode
    )


@app.route("/noticia/<path:uri>")
def detalle_noticia(uri):
    lang = request.args.get('lang', 'es')
    dark_mode = request.cookies.get('dark_mode', 'true') == 'true'
    keyword = request.args.get('keyword', '')
    
    uri_decoded = urllib.parse.unquote(uri)
    detalles = {}
    
    try:
        query = f"""
            PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            
            SELECT ?propiedad ?valor
            WHERE {{
                <{uri_decoded}> ?propiedad ?valor .
                FILTER (
                    STRSTARTS(STR(?propiedad), 
                        "http://www.semanticweb.org/cabez/ontologies/2025/2/untitled-ontology-3#") ||
                    ?propiedad IN (rdf:type, rdfs:label, rdfs:comment)
                )
            }}
        """
        
        for row in graph.query(query):
            prop_name = str(row.propiedad).split("#")[-1]
            valor = str(row.valor)
            
            if hasattr(row.valor, 'toPython'):
                valor = str(row.valor.toPython())
            
            detalles[prop_name] = valor
    
    except Exception as e:
        print(f"Error obteniendo detalles: {e}")
    
    inferred = infer_properties(graph, URIRef(uri_decoded))
    
    return render_template(
        "detalle.html",
        noticia=detalles,
        inferred=inferred,
        translations=NewsSearchConfig.TRANSLATIONS,
        languages=NewsSearchConfig.LANGUAGES,
        current_lang=lang,
        dark_mode=dark_mode,
        keyword=keyword
    )


@app.route("/toggle_dark_mode", methods=["POST"])
def toggle_dark_mode():
    dark_mode = request.json.get('dark_mode', True)
    response = jsonify({"success": True})
    response.set_cookie('dark_mode', str(dark_mode).lower(), max_age=31536000)
    return response


@app.route("/stats", methods=["GET"])
def get_stats():
    return jsonify({
        "ontology": {
            "triples": len(graph),
            "resources": len(list(graph.subjects()))
        },
        "dbpedia_local": dbpedia_index.get_statistics(),
        "supported_languages": NewsSearchConfig.LANGUAGES
    })


if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)