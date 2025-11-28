"""
Gestor de DBpedia local para búsquedas sin conexión a internet.
Implementa un índice en memoria con datos de DBpedia descargados localmente.
"""

import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime


@dataclass
class DBpediaResource:
    """Representa un recurso de DBpedia."""
    uri: str
    label: str
    abstract: str
    language: str = "en"
    categories: List[str] = field(default_factory=list)
    properties: Dict[str, Any] = field(default_factory=dict)
    thumbnail: Optional[str] = None
    birthDate: Optional[str] = None
    deathDate: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convierte el recurso a diccionario."""
        return asdict(self)


class DBpediaLocalIndex:
    """Índice local de recursos DBpedia con búsqueda rápida."""
    
    def __init__(self, db_file: str = "data/dbpedia_local.json"):
        self.db_file = Path(db_file)
        self.resources: Dict[str, DBpediaResource] = {}
        self.label_index: Dict[str, List[str]] = {}
        self.category_index: Dict[str, List[str]] = {}
        self.load_or_initialize()
    
    def load_or_initialize(self) -> None:
        """Carga la base de datos local o inicializa una nueva."""
        if self.db_file.exists():
            self._load_from_file()
        else:
            self._initialize_default_data()
    
    def _load_from_file(self) -> None:
        """Carga recursos desde archivo JSON."""
        try:
            with open(self.db_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            for uri, resource_data in data.items():
                resource = DBpediaResource(**resource_data)
                self.resources[uri] = resource
                self._index_resource(resource)
            
            print(f"✓ Cargados {len(self.resources)} recursos de DBpedia local")
        except Exception as e:
            print(f"✗ Error cargando DBpedia local: {e}")
            self._initialize_default_data()
    
    def _initialize_default_data(self) -> None:
        """Inicializa datos por defecto en caso de no existir archivo."""
        default_resources = [
            {
                "uri": "http://dbpedia.org/resource/Bolivia",
                "label": "Bolivia",
                "abstract": "Bolivia es un país ubicado en Sudamérica. Comparte fronteras con Brasil, Perú, Chile, Argentina y Paraguay.",
                "categories": ["Countries", "South America"],
                "properties": {"capital": "La Paz", "population": "11,832,940"}
            },
            {
                "uri": "http://dbpedia.org/resource/Cochabamba",
                "label": "Cochabamba",
                "abstract": "Cochabamba es una ciudad ubicada en el valle del Cochabamba, en el centro de Bolivia.",
                "categories": ["Cities in Bolivia"],
                "properties": {"country": "Bolivia", "elevation": "2558m"}
            },
            {
                "uri": "http://dbpedia.org/resource/La_Paz",
                "label": "La Paz",
                "abstract": "La Paz es la capital administrativo de Bolivia y la sede de los organismos ejecutivo y legislativo.",
                "categories": ["Capitals of South America"],
                "properties": {"country": "Bolivia", "elevation": "3650m"}
            },
            {
                "uri": "http://dbpedia.org/resource/Dengue",
                "label": "Dengue",
                "abstract": "El dengue es una enfermedad infecciosa causada por el virus del dengue.",
                "categories": ["Infectious diseases", "Tropical diseases"],
                "properties": {"virus": "Dengue virus", "transmission": "Mosquito"}
            },
            {
                "uri": "http://dbpedia.org/resource/COVID-19",
                "label": "COVID-19",
                "abstract": "COVID-19 es la enfermedad infecciosa causada por el coronavirus SARS-CoV-2.",
                "categories": ["Pandemic", "Infectious diseases"],
                "properties": {"pathogen": "SARS-CoV-2", "firstCase": "2019"}
            }
        ]
        
        for res_data in default_resources:
            resource = DBpediaResource(**res_data)
            self.resources[resource.uri] = resource
            self._index_resource(resource)
        
        self._save_to_file()
    
    def _index_resource(self, resource: DBpediaResource) -> None:
        """Indexa un recurso para búsqueda rápida."""
        label_lower = resource.label.lower()
        if label_lower not in self.label_index:
            self.label_index[label_lower] = []
        self.label_index[label_lower].append(resource.uri)
        
        for category in resource.categories:
            category_lower = category.lower()
            if category_lower not in self.category_index:
                self.category_index[category_lower] = []
            self.category_index[category_lower].append(resource.uri)
    
    def search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Busca recursos que coincidan con la consulta.
        
        Args:
            query: Término de búsqueda
            limit: Número máximo de resultados
            
        Returns:
            Lista de recursos encontrados
        """
        query_lower = query.lower()
        results = []
        
        for uri, resource in self.resources.items():
            score = self._calculate_relevance(resource, query_lower)
            if score > 0:
                results.append({
                    "resource": {"value": resource.uri},
                    "label": {"value": resource.label},
                    "abstract": {"value": resource.abstract},
                    "score": score
                })
        
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:limit]
    
    def _calculate_relevance(self, resource: DBpediaResource, query: str) -> float:
        """
        Calcula la relevancia de un recurso para una consulta.
        
        Args:
            resource: Recurso a evaluar
            query: Consulta en minúsculas
            
        Returns:
            Puntuación de relevancia (0-100)
        """
        score = 0.0
        label_lower = resource.label.lower()
        
        if label_lower == query:
            score += 100
        elif label_lower.startswith(query):
            score += 80
        elif query in label_lower:
            score += 50
        
        abstract_lower = resource.abstract.lower()
        if query in abstract_lower:
            score += 20
        
        return score
    
    def get_by_uri(self, uri: str) -> Optional[Dict[str, Any]]:
        """Obtiene un recurso por su URI."""
        if uri in self.resources:
            return asdict(self.resources[uri])
        return None
    
    def add_resource(self, resource: DBpediaResource) -> None:
        """Añade un nuevo recurso al índice."""
        self.resources[resource.uri] = resource
        self._index_resource(resource)
        self._save_to_file()
    
    def _save_to_file(self) -> None:
        """Guarda los recursos en archivo JSON."""
        self.db_file.parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            uri: resource.to_dict() 
            for uri, resource in self.resources.items()
        }
        
        with open(self.db_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def export_sparql_compatible(self) -> Dict[str, List[Dict[str, Dict[str, str]]]]:
        """
        Exporta los datos en formato compatible con respuestas SPARQL.
        Útil para mantener compatibilidad con código existente.
        """
        results = []
        for uri, resource in self.resources.items():
            results.append({
                "resource": {"value": resource.uri},
                "label": {"value": resource.label},
                "abstract": {"value": resource.abstract}
            })
        return {"results": {"bindings": results}}
    
    def get_statistics(self) -> Dict[str, Any]:
        """Retorna estadísticas del índice."""
        return {
            "total_resources": len(self.resources),
            "total_categories": len(self.category_index),
            "total_indexed_labels": len(self.label_index),
            "last_updated": datetime.now().isoformat()
        }


class HybridSearchEngine:
    """Motor de búsqueda que combina índice local con búsquedas online."""
    
    def __init__(self, dbpedia_index: DBpediaLocalIndex, online_searcher=None):
        self.local_index = dbpedia_index
        self.online_searcher = online_searcher
    
    def search(self, query: str, use_online: bool = True, 
               limit: int = 5) -> Dict[str, Any]:
        """
        Realiza búsqueda en índice local y opcionalmente en línea.
        
        Args:
            query: Término de búsqueda
            use_online: Si se debe intentar búsqueda online
            limit: Límite de resultados
            
        Returns:
            Dict con resultados locales y online
        """
        local_results = self.local_index.search(query, limit)
        online_results = []
        
        if use_online and self.online_searcher:
            try:
                online_results = self.online_searcher.query_dbpedia(query)
            except Exception as e:
                print(f"⚠ Búsqueda online no disponible: {e}")
        
        return {
            "local": {
                "count": len(local_results),
                "results": local_results
            },
            "online": {
                "count": len(online_results),
                "results": online_results
            },
            "total": len(local_results) + len(online_results)
        }


def initialize_dbpedia() -> DBpediaLocalIndex:
    """Factory para inicializar el índice de DBpedia."""
    return DBpediaLocalIndex()