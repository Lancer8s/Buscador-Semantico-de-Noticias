"""
init_dbpedia.py
Script para inicializar y expandir la base de datos local de DBpedia.
"""

import json
from pathlib import Path
from dbpedia_manager import DBpediaLocalIndex, DBpediaResource
from SPARQLWrapper import SPARQLWrapper, JSON


def expand_dbpedia_with_sparql(index: DBpediaLocalIndex, 
                               topics: list = None,
                               limit_per_topic: int = 10) -> None:
    """Expande el índice local descargando datos de DBpedia."""
    
    if topics is None:
        topics = [
            "Bolivia",
            "Dengue",
            "COVID-19",
            "Fake news",
            "Fact-checking",
            "Journalism",
            "News media"
        ]
    
    sparql = SPARQLWrapper("http://dbpedia.org/sparql")
    sparql.setReturnFormat(JSON)
    
    print("📥 Descargando datos de DBpedia...\n")
    
    for topic in topics:
        print(f"  📖 Tópico: {topic}")
        
        query = f"""
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX dbo: <http://dbpedia.org/ontology/>
            
            SELECT DISTINCT ?resource ?label ?abstract WHERE {{
                ?resource rdfs:label ?label .
                FILTER(LANG(?label) = "en")
                FILTER(CONTAINS(LCASE(STR(?label)), LCASE("{topic}")))
                
                OPTIONAL {{ 
                    ?resource dbo:abstract ?abstract .
                    FILTER(LANG(?abstract) = "en") 
                }}
                
                FILTER(STRSTARTS(STR(?resource), "http://dbpedia.org/resource/"))
            }}
            LIMIT {limit_per_topic}
        """
        
        try:
            sparql.setQuery(query)
            results = sparql.query().convert()
            
            for binding in results["results"]["bindings"]:
                uri = binding["resource"]["value"]
                label = binding["label"]["value"]
                abstract = binding.get("abstract", {}).get("value", "")
                
                resource = DBpediaResource(
                    uri=uri,
                    label=label,
                    abstract=abstract,
                    language="en",
                    categories=["DBpedia", topic]
                )
                
                index.add_resource(resource)
                print(f"    ✓ {label}")
            
            print(f"    ✓ {len(results['results']['bindings'])} recursos agregados\n")
        
        except Exception as e:
            print(f"    ✗ Error: {e}\n")
    
    print("✅ Base de datos expandida\n")


def add_spanish_translations(index: DBpediaLocalIndex) -> None:
    """Agrega traducciones al español de recursos clave."""
    
    print("🌐 Agregando traducciones al español...\n")
    
    spanish_resources = {
        "http://dbpedia.org/resource/Bolivia": {
            "label": "Bolivia",
            "abstract": "Bolivia es un país ubicado en Sudamérica. Limita con Brasil, Perú, Chile, Argentina y Paraguay."
        },
        "http://dbpedia.org/resource/Dengue": {
            "label": "Dengue",
            "abstract": "El dengue es una enfermedad infecciosa viral transmitida por mosquitos del género Aedes."
        },
        "http://dbpedia.org/resource/COVID-19": {
            "label": "COVID-19",
            "abstract": "COVID-19 es la enfermedad infecciosa causada por el coronavirus SARS-CoV-2."
        }
    }
    
    for uri, data in spanish_resources.items():
        if uri in index.resources:
            resource = index.resources[uri]
            index.resources[uri + "_es"] = DBpediaResource(
                uri=uri + "_es",
                label=data["label"],
                abstract=data["abstract"],
                language="es",
                categories=resource.categories
            )
            print(f"  ✓ {data['label']}")
    
    index._save_to_file()
    print("✅ Traducciones agregadas\n")


def print_statistics(index: DBpediaLocalIndex) -> None:
    """Imprime estadísticas de la base de datos."""
    stats = index.get_statistics()
    
    print("="*50)
    print("📊 ESTADÍSTICAS DE DBPEDIA LOCAL")
    print("="*50)
    print(f"Recursos totales: {stats['total_resources']}")
    print(f"Categorías: {stats['total_categories']}")
    print(f"Etiquetas indexadas: {stats['total_indexed_labels']}")
    print(f"Última actualización: {stats['last_updated']}")
    print("="*50 + "\n")


def main() -> None:
    """Inicializa DBpedia local."""
    
    print("\n🚀 INICIALIZANDO DBPEDIA LOCAL")
    print("="*50 + "\n")
    
    index = DBpediaLocalIndex()
    
    print("¿Deseas expandir la base de datos descargando de DBpedia online?")
    print("(Requiere conexión a internet)\n")
    response = input("Sí/No [S/n]: ").lower().strip()
    
    if response != 'n':
        try:
            expand_dbpedia_with_sparql(index, limit_per_topic=5)
            add_spanish_translations(index)
        except Exception as e:
            print(f"⚠️  Error expandiendo DBpedia: {e}")
            print("Continuando con datos por defecto...\n")
    
    print_statistics(index)
    print("✅ Inicialización completada\n")


if __name__ == "__main__":
    main()