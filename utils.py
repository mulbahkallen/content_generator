from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any

@dataclass
class BrandInfo:
    name: str
    industry: str
    location: str
    voice_tone: str
    target_audience: str
    uvp: str
    notes: str

@dataclass
class PageDefinition:
    slug: str
    page_name: str
    page_type: str  # "home", "service", "about", "location"

@dataclass
class SEOEntry:
    slug: str
    primary_keyword: Optional[str] = None
    supporting_keywords: List[str] = field(default_factory=list)

SEOMap = Dict[str, SEOEntry]
