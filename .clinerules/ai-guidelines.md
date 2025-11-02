# Règles d'Utilisation de l'IA - WindFlow

## Vue d'Ensemble

Ce document définit les règles pour l'utilisation de l'intelligence artificielle dans le projet WindFlow. L'IA est intégrée comme assistant de développement collaboratif pour améliorer la productivité, la qualité du code et l'efficacité des déploiements, tout en respectant les principes de sécurité et de maintenabilité.

## Philosophie d'Utilisation de l'IA

### 1. IA Collaborative et Augmentée
- **Partenariat Humain-IA** : L'IA complète l'expertise humaine sans la remplacer
- **Validation Humaine** : Toute suggestion IA doit être validée par un développeur expérimenté
- **Transparence** : Toutes les modifications générées par IA doivent être documentées
- **Apprentissage Continu** : Feedback constant pour améliorer les suggestions IA

### 2. Respect du Contexte WindFlow
- **Architecture-Aware** : Comprendre l'architecture microservices et event-driven
- **Stack-Specific** : Respecter les technologies (FastAPI, Vue.js 3, Docker, Kubernetes)
- **Convention-Driven** : Suivre strictement les conventions définies dans `.clinerules/`
- **Domain-Focused** : Spécialisé dans le déploiement de containers et l'orchestration

### 3. Qualité et Sécurité Prioritaires
- **Security by Design** : Intégrer la sécurité dès la conception
- **Type Safety** : Maintenir le type safety strict (Python type hints, TypeScript)
- **Test-Driven** : Générer automatiquement les tests appropriés
- **Performance-Conscious** : Optimiser pour les workloads de déploiement
- 
### 3. Langues et traduction
- **Code** : Tous les noms de méthodes, classes en variables dans le code sont en anglais
- **Commentaires** : Tous les commentaires dans le code sont en anglais
- **Documents officiels** : les documents officiels (README.md, SECURITY.md, CHANGELOG.md, CONTRIBUTIONG.md) que l'on trouve sur la racine du projet sont en anglais
- **Documentation** : Les documents présents dans le répertoire doc et ses sous répertoires sont en français
- 
## Intégration LLM dans WindFlow

### Configuration LiteLLM Multi-Provider

WindFlow utilise LiteLLM pour l'intégration multi-provider d'IA :

```python
# windflow/core/llm_config.py
from pydantic import BaseModel
from typing import Optional, Dict, Any

class LLMConfig(BaseModel):
    """Configuration pour l'intégration LLM dans WindFlow."""
    
    # Provider configuration
    provider: str = "openai"  # openai, anthropic, ollama, azure
    model: str = "gpt-4-turbo-preview"
    base_url: Optional[str] = None  # Pour Ollama local
    api_key: Optional[str] = None
    
    # Generation parameters
    temperature: float = 0.1  # Bas pour la cohérence du code
    max_tokens: int = 2000
    top_p: float = 0.9
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0
    
    # WindFlow specific
    context_window: int = 8192
    enable_function_calling: bool = True
    enable_streaming: bool = False
    
    # Safety and filtering
    content_filter: bool = True
    bias_detection: bool = True
    code_review_mode: bool = True

# Utilisation avec différents providers
# Local Ollama pour développement
ollama_config = LLMConfig(
    provider="ollama",
    model="codellama:13b",
    base_url="http://localhost:11434",
    temperature=0.1
)

# OpenAI pour production
openai_config = LLMConfig(
    provider="openai",
    model="gpt-4-turbo-preview",
    api_key="${OPENAI_API_KEY}",
    temperature=0.1
)
```

### Service LLM Intelligent pour WindFlow

```python
# windflow/services/llm_service.py
from typing import Dict, Any, List, Optional, Tuple
import logging
from litellm import completion, acompletion
from windflow.core.llm_config import LLMConfig
from windflow.exceptions import LLMServiceError

logger = logging.getLogger(__name__)

class WindFlowLLMService:
    """Service LLM spécialisé pour les tâches WindFlow."""
    
    def __init__(self, config: LLMConfig):
        self.config = config
        self.context_templates = self._load_context_templates()
        
    async def optimize_deployment_config(
        self,
        config: Dict[str, Any],
        target_type: str,
        constraints: Optional[Dict[str, Any]] = None
    ) -> Tuple[Dict[str, Any], Optional[str]]:
        """Optimise une configuration de déploiement via LLM.
        
        Args:
            config: Configuration de déploiement initiale
            target_type: Type de cible (docker, kubernetes, vm, physical)
            constraints: Contraintes de ressources optionnelles
            
        Returns:
            Tuple[Dict, str]: Configuration optimisée et erreur éventuelle
            
        Example:
            >>> config = {"services": {"web": {"image": "nginx"}}}
            >>> optimized, error = await llm_service.optimize_deployment_config(
            ...     config, "kubernetes", {"cpu_limit": "2", "memory_limit": "4Gi"}
            ... )
        """
        try:
            system_prompt = self._build_optimization_prompt(target_type, constraints)
            user_prompt = f"""
            Optimise cette configuration de déploiement pour {target_type}:
            
            Configuration actuelle:
            {config}
            
            Contraintes:
            {constraints or "Aucune contrainte spécifiée"}
            
            Fournis une configuration optimisée en JSON avec les améliorations suivantes:
            1. Optimisation des ressources (CPU, mémoire)
            2. Sécurisation (security context, network policies)
            3. Bonnes pratiques de production
            4. Health checks et monitoring
            5. Scaling automatique si applicable
            
            Retourne UNIQUEMENT le JSON optimisé sans explication.
            """
            
            response = await acompletion(
                model=self.config.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens
            )
            
            optimized_config = self._parse_json_response(response.choices[0].message.content)
            if optimized_config is None:
                return config, "Erreur de parsing de la réponse LLM"
                
            # Validation de la configuration optimisée
            validation_error = await self._validate_optimized_config(optimized_config, target_type)
            if validation_error:
                return config, validation_error
                
            logger.info(f"Configuration optimisée avec succès pour {target_type}")
            return optimized_config, None
            
        except Exception as e:
            logger.error(f"Erreur lors de l'optimisation LLM: {e}")
            return config, str(e)
    
    async def generate_infrastructure_code(
        self,
        requirements: Dict[str, Any],
        platform: str = "terraform"
    ) -> Tuple[str, Optional[str]]:
        """Génère du code d'infrastructure as code.
        
        Args:
            requirements: Exigences d'infrastructure
            platform: Plateforme cible (terraform, ansible, helm)
            
        Returns:
            Tuple[str, str]: Code généré et erreur éventuelle
        """
        try:
            system_prompt = self._build_iac_prompt(platform)
            user_prompt = f"""
            Génère du code {platform} pour ces exigences d'infrastructure:
            
            {requirements}
            
            Le code doit inclure:
            1. Bonnes pratiques de sécurité
            2. Monitoring et logging
            3. Backup et disaster recovery
            4. Network segmentation
            5. Resource tagging et cost management
            
            Respecte les conventions WindFlow et inclus des commentaires explicatifs.
            """
            
            response = await acompletion(
                model=self.config.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens
            )
            
            generated_code = response.choices[0].message.content
            
            # Validation du code généré
            validation_error = await self._validate_generated_code(generated_code, platform)
            if validation_error:
                return "", validation_error
                
            return generated_code, None
            
        except Exception as e:
            logger.error(f"Erreur lors de la génération de code: {e}")
            return "", str(e)
    
    async def analyze_deployment_logs(
        self,
        logs: List[str],
        deployment_context: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], Optional[str]]:
        """Analyse les logs de déploiement pour identifier les problèmes.
        
        Args:
            logs: Liste des entrées de log
            deployment_context: Contexte du déploiement
            
        Returns:
            Tuple[Dict, str]: Analyse et recommandations
        """
        try:
            system_prompt = """
            Tu es un expert en analyse de logs de déploiement Docker/Kubernetes.
            Analyse les logs pour identifier:
            1. Erreurs et warnings critiques
            2. Problèmes de performance
            3. Problèmes de sécurité
            4. Recommandations d'amélioration
            
            Fournis une analyse structurée en JSON.
            """
            
            # Limiter les logs pour éviter le dépassement de contexte
            truncated_logs = logs[-100:] if len(logs) > 100 else logs
            
            user_prompt = f"""
            Contexte du déploiement:
            {deployment_context}
            
            Logs à analyser:
            {chr(10).join(truncated_logs)}
            
            Retourne l'analyse en JSON avec cette structure:
            {{
                "severity": "low|medium|high|critical",
                "issues": [
                    {{
                        "type": "error|warning|performance|security",
                        "description": "Description du problème",
                        "recommendation": "Recommandation de résolution",
                        "code_examples": "Exemples de code si applicable"
                    }}
                ],
                "summary": "Résumé de l'analyse",
                "next_steps": ["Actions recommandées"]
            }}
            """
            
            response = await acompletion(
                model=self.config.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,  # Très bas pour analyse factuelle
                max_tokens=self.config.max_tokens
            )
            
            analysis = self._parse_json_response(response.choices[0].message.content)
            if analysis is None:
                return {}, "Erreur de parsing de l'analyse"
                
            return analysis, None
            
        except Exception as e:
            logger.error(f"Erreur lors de l'analyse des logs: {e}")
            return {}, str(e)
```

## Patterns de Code Assistés par IA

### 1. Génération de Services Backend

L'IA peut assister dans la génération de services FastAPI en respectant les patterns WindFlow :

```python
# Prompt pour génération de service
BACKEND_SERVICE_PROMPT = """
Génère un service FastAPI pour WindFlow avec les caractéristiques suivantes:
- Type hints complets et strict
- Docstrings Google Style
- Pattern Repository avec Dependency Injection
- Gestion d'erreurs avec exceptions WindFlow
- Logging structuré avec contexte
- Métriques Prometheus intégrées
- Tests pytest avec fixtures appropriées

Service à créer: {service_description}
Modèles de données: {data_models}
Endpoints requis: {endpoints}

Respecte la structure:
- windflow/services/{service_name}_service.py
- windflow/schemas/{service_name}.py
- tests/unit/test_services/test_{service_name}_service.py
"""
```

### 2. Génération de Composants Frontend

```typescript
// Prompt pour composants Vue.js 3
const FRONTEND_COMPONENT_PROMPT = `
Génère un composant Vue.js 3 pour WindFlow avec:
- Composition API obligatoire
- TypeScript strict avec interfaces complètes
- Element Plus pour l'UI
- UnoCSS pour le styling
- Props et emits typés
- Gestion d'erreur avec stores Pinia
- Tests Vitest avec Vue Test Utils

Composant à créer: {component_description}
Props requises: {props}
Events émis: {events}
Intégrations API: {api_endpoints}

Structure:
- src/components/features/{ComponentName}.vue
- tests/unit/components/{ComponentName}.test.ts
`;
```

### 3. Génération de Commandes CLI

```python
# Prompt pour commandes CLI
CLI_COMMAND_PROMPT = """
Génère une commande CLI WindFlow avec:
- Rich pour l'affichage moderne
- Typer pour les arguments type-safe
- Gestion d'erreurs avec codes de retour appropriés
- Progress bars et feedback utilisateur
- Configuration hiérarchique
- Tests avec CliRunner

Commande à créer: {command_description}
Arguments: {arguments}
Options: {options}
Intégrations API: {api_calls}

Structure:
- cli/commands/{command_name}.py
- tests/unit/test_commands/test_{command_name}.py
"""
```

## Optimisation Intelligente des Déploiements

### Configuration avec IA pour Kubernetes

```python
# windflow/ai/deployment_optimizer.py
from typing import Dict, Any, List
from windflow.services.llm_service import WindFlowLLMService

class AIDeploymentOptimizer:
    """Optimiseur de déploiements assisté par IA."""
    
    def __init__(self, llm_service: WindFlowLLMService):
        self.llm_service = llm_service
        
    async def optimize_kubernetes_manifest(
        self,
        manifest: Dict[str, Any],
        cluster_info: Dict[str, Any],
        workload_patterns: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Optimise un manifeste Kubernetes avec l'IA.
        
        L'IA analyse:
        1. Les patterns de charge historiques
        2. Les caractéristiques du cluster
        3. Les bonnes pratiques Kubernetes
        4. Les optimisations de sécurité
        """
        
        constraints = {
            "cluster_resources": cluster_info,
            "historical_patterns": workload_patterns,
            "security_requirements": ["pod_security_standard", "network_policies"],
            "performance_targets": {
                "max_startup_time": "30s",
                "resource_efficiency": "> 80%",
                "availability": "99.9%"
            }
        }
        
        optimized_manifest, error = await self.llm_service.optimize_deployment_config(
            manifest,
            "kubernetes",
            constraints
        )
        
        if error:
            raise DeploymentOptimizationError(f"Erreur d'optimisation IA: {error}")
            
        # Post-processing et validation
        validated_manifest = await self._validate_kubernetes_manifest(optimized_manifest)
        return validated_manifest
    
    async def suggest_resource_allocation(
        self,
        service_metrics: Dict[str, Any],
        cluster_capacity: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Suggère une allocation de ressources optimale."""
        
        prompt = f"""
        Analyse ces métriques de service et suggère une allocation optimale:
        
        Métriques actuelles: {service_metrics}
        Capacité cluster: {cluster_capacity}
        
        Considère:
        1. CPU et mémoire utilisés vs alloués
        2. Patterns de charge (pics, moyennes)
        3. Temps de démarrage et scaling
        4. Coût vs performance
        
        Retourne des recommandations de requests/limits optimales.
        """
        
        # Appel LLM pour analyse et recommandations
        response = await self.llm_service.analyze_and_recommend(prompt)
        return response
```

### Génération de Docker Compose Intelligent

```python
async def generate_docker_compose(
    self,
    services_description: List[Dict[str, Any]],
    environment: str = "production"
) -> str:
    """Génère un docker-compose.yml optimisé avec l'IA."""
    
    prompt = f"""
    Génère un docker-compose.yml pour ces services:
    {services_description}
    
    Environnement: {environment}
    
    Inclus obligatoirement:
    1. Health checks pour tous les services
    2. Resource limits appropriées
    3. Networks isolés par fonction
    4. Volumes persistants pour les données
    5. Secrets management avec Docker Secrets
    6. Logging centralisé
    7. Monitoring avec Prometheus/Grafana
    8. Backup automatique pour les bases de données
    
    Optimise pour:
    - Sécurité (non-root users, read-only filesystems)
    - Performance (cache layers, multi-stage builds)
    - Observabilité (metrics, tracing, logs)
    - Haute disponibilité (replicas, restart policies)
    """
    
    compose_content, error = await self.llm_service.generate_infrastructure_code(
        {"services": services_description, "environment": environment},
        "docker-compose"
    )
    
    return compose_content
```

## Analyse de Code et Review Automatisé

### Code Review Assistant

```python
# windflow/ai/code_reviewer.py
class AICodeReviewer:
    """Assistant IA pour le review de code WindFlow."""
    
    async def review_pull_request(
        self,
        diff: str,
        file_contexts: Dict[str, str],
        pr_description: str
    ) -> Dict[str, Any]:
        """Review automatique d'une pull request."""
        
        review_prompt = f"""
        Tu es un expert WindFlow senior reviewer. Analyse cette PR:
        
        Description: {pr_description}
        Diff: {diff}
        
        Vérifie:
        1. Respect des conventions .clinerules/
        2. Type safety (Python type hints, TypeScript strict)
        3. Sécurité (injection, authentification, autorisation)
        4. Performance (requêtes N+1, cache, async/await)
        5. Tests (couverture, qualité, edge cases)
        6. Documentation (docstrings, README, API docs)
        7. Architecture (coupling, cohésion, patterns)
        
        Identifie:
        - Bugs potentiels
        - Problèmes de sécurité
        - Optimisations possibles
        - Non-conformités aux règles
        
        Fournis des suggestions constructives avec exemples de code.
        """
        
        review = await self.llm_service.analyze_code(review_prompt)
        return review
    
    async def suggest_improvements(
        self,
        code: str,
        language: str,
        context: str = ""
    ) -> List[Dict[str, str]]:
        """Suggère des améliorations de code."""
        
        improvement_prompt = f"""
        Analyse ce code {language} WindFlow et suggère des améliorations:
        
        Code:
        {code}
        
        Contexte: {context}
        
        Cherche des opportunités pour:
        1. Optimisation des performances
        2. Amélioration de la lisibilité
        3. Réduction de la complexité
        4. Meilleure gestion d'erreurs
        5. Patterns plus appropriés
        
        Pour chaque suggestion, fournis:
        - Description du problème
        - Solution recommandée
        - Exemple de code amélioré
        - Impact estimé (performance, maintenabilité)
        """
        
        improvements = await self.llm_service.get_code_suggestions(improvement_prompt)
        return improvements
```

## Sécurité et Validation

### Validation des Sorties IA

```python
# windflow/ai/validators.py
class AIOutputValidator:
    """Validateur pour les sorties IA."""
    
    async def validate_generated_code(
        self,
        code: str,
        language: str,
        context: Dict[str, Any]
    ) -> Tuple[bool, List[str]]:
        """Valide le code généré par IA."""
        
        errors = []
        
        # Validation syntaxique
        if not await self._check_syntax(code, language):
            errors.append("Erreur de syntaxe détectée")
        
        # Validation de sécurité
        security_issues = await self._check_security(code, language)
        errors.extend(security_issues)
        
        # Validation des conventions
        convention_issues = await self._check_conventions(code, language, context)
        errors.extend(convention_issues)
        
        # Validation des performances
        performance_issues = await self._check_performance(code, language)
        errors.extend(performance_issues)
        
        return len(errors) == 0, errors
    
    async def _check_security(self, code: str, language: str) -> List[str]:
        """Vérifie les problèmes de sécurité."""
        issues = []
        
        # Patterns de sécurité à vérifier
        security_patterns = {
            "sql_injection": r"f?['\"].*\{.*\}.*['\"].*execute",
            "hardcoded_secrets": r"(password|token|key|secret)\s*=\s*['\"][^'\"]+['\"]",
            "unsafe_yaml": r"yaml\.load\(",
            "eval_usage": r"\beval\s*\(",
            "shell_injection": r"os\.system|subprocess\.call.*shell=True"
        }
        
        for pattern_name, pattern in security_patterns.items():
            if re.search(pattern, code, re.IGNORECASE):
                issues.append(f"Problème de sécurité potentiel: {pattern_name}")
        
        return issues
```

### Filtrage de Contenu

```python
class AIContentFilter:
    """Filtre de contenu pour les interactions IA."""
    
    def __init__(self):
        self.blocked_patterns = [
            r"rm\s+-rf\s+/",  # Commandes destructives
            r"sudo\s+chmod\s+777",  # Permissions dangereuses
            r"--allow-root",  # Exécution en root
            r"trust.*certificate",  # Certificats non vérifiés
            r"disable.*ssl.*verify",  # SSL désactivé
        ]
    
    def filter_prompt(self, prompt: str) -> Tuple[str, List[str]]:
        """Filtre et nettoie les prompts."""
        warnings = []
        filtered_prompt = prompt
        
        for pattern in self.blocked_patterns:
            if re.search(pattern, prompt, re.IGNORECASE):
                warnings.append(f"Pattern potentiellement dangereux détecté: {pattern}")
                # Masquer ou supprimer le pattern
                filtered_prompt = re.sub(pattern, "[FILTERED]", filtered_prompt, flags=re.IGNORECASE)
        
        return filtered_prompt, warnings
```

## Monitoring et Métriques IA

### Métriques de Performance IA

```python
# windflow/ai/metrics.py
from prometheus_client import Counter, Histogram, Gauge

# Métriques spécifiques à l'IA
AI_REQUESTS_TOTAL = Counter(
    'windflow_ai_requests_total',
    'Nombre total de requêtes IA',
    ['provider', 'model', 'operation_type', 'status']
)

AI_REQUEST_DURATION = Histogram(
    'windflow_ai_request_duration_seconds',
    'Durée des requêtes IA',
    ['provider', 'model', 'operation_type'],
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, float('inf'))
)

AI_TOKEN_USAGE = Counter(
    'windflow_ai_tokens_total',
    'Utilisation des tokens IA',
    ['provider', 'model', 'token_type']  # prompt_tokens, completion_tokens
)

AI_QUALITY_SCORE = Gauge(
    'windflow_ai_quality_score',
    'Score de qualité des sorties IA',
    ['operation_type']
)

class AIMetricsCollector:
    """Collecteur de métriques pour les opérations IA."""
    
    def record_ai_request(
        self,
        provider: str,
        model: str,
        operation_type: str,
        duration: float,
        status: str,
        token_usage: Dict[str, int]
    ):
        """Enregistre les métriques d'une requête IA."""
        
        AI_REQUESTS_TOTAL.labels(
            provider=provider,
            model=model,
            operation_type=operation_type,
            status=status
        ).inc()
        
        AI_REQUEST_DURATION.labels(
            provider=provider,
            model=model,
            operation_type=operation_type
        ).observe(duration)
        
        for token_type, count in token_usage.items():
            AI_TOKEN_USAGE.labels(
                provider=provider,
                model=model,
                token_type=token_type
            ).inc(count)
```

## Bonnes Pratiques et Limitations

### Guidelines d'Utilisation

1. **Validation Humaine Obligatoire**
   - Tout code généré par IA doit être reviewé par un développeur
   - Tests automatisés obligatoires pour le code généré
   - Documentation des modifications IA dans les commits

2. **Sécurité et Conformité**
   - Jamais de secrets ou données sensibles dans les prompts
   - Validation automatique des sorties IA
   - Audit trail complet des interactions IA

3. **Performance et Coûts**
   - Monitoring des coûts d'utilisation des APIs LLM
   - Cache intelligent des réponses fréquentes
   - Fallback en cas d'indisponibilité des services IA

4. **Maintenance et Évolution**
   - Versioning des prompts et templates IA
   - A/B testing des nouvelles versions de prompts
   - Feedback loop pour améliorer la qualité

### Limitations et Précautions

```python
# windflow/ai/limitations.py
class AILimitations:
    """Documentation des limitations IA pour WindFlow."""
    
    KNOWN_LIMITATIONS = {
        "code_generation": [
            "Peut générer du code syntaxiquement correct mais logiquement incorrect",
            "Difficultés avec le contexte métier spécifique",
            "Tendance à sur-complexifier les solutions simples"
        ],
        "infrastructure_optimization": [
            "Manque de connaissance des contraintes matérielles spécifiques",
            "Optimisations génériques qui peuvent ne pas s'appliquer",
            "Difficultés avec les configurations très spécialisées"
        ],
        "security_analysis": [
            "Peut manquer des vulnérabilités sophistiquées",
            "Faux positifs sur les alertes de sécurité",
            "Évolution rapide des menaces non prise en compte"
        ]
    }
    
    MITIGATION_STRATEGIES = {
        "human_oversight": "Validation humaine systématique",
        "automated_testing": "Tests automatisés complets",
        "security_scanning": "Outils de sécurité automatisés",
        "performance_monitoring": "Monitoring continu des performances",
        "gradual_rollout": "Déploiement progressif des changements IA"
    }
```

## Configuration et Déploiement

### Variables d'Environnement

```bash
# Configuration IA WindFlow
WINDFLOW_LLM_PROVIDER=ollama
WINDFLOW_LLM_MODEL=codellama:13b
WINDFLOW_LLM_BASE_URL=http://localhost:11434
WINDFLOW_LLM_TEMPERATURE=0.1
WINDFLOW_LLM_MAX_TOKENS=2000

# Sécurité
WINDFLOW_AI_CONTENT_FILTER=true
WINDFLOW_AI_RATE_LIMIT=100  # requêtes par heure
WINDFLOW_AI_AUDIT_LOG=true

# Métriques
WINDFLOW_AI_METRICS_ENABLED=true
WINDFLOW_AI_QUALITY_THRESHOLD=0.8
```

### Intégration CI/CD

```yaml
# .github/workflows/ai-validation.yml
name: AI Code Validation

on:
  pull_request:
    types: [opened, synchronize]

jobs:
  ai-review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: AI Code Review
        run: |
          python -m windflow.ai.code_reviewer \
            --diff="${{ github.event.pull_request.diff_url }}" \
            --output=review.json
      
      - name: Post Review Comments
        uses: actions/github-script@v6
        with:
          script: |
            const review = require('./review.json');
            // Poster les commentaires de review automatiques
```

---

**Note Importante** : L'IA est un outil puissant mais elle doit être utilisée avec discernement. La responsabilité finale du code et de l'architecture reste toujours aux développeurs humains. Ce document sera mis à jour régulièrement basé sur les retours d'expérience et l'évolution des technologies IA.

**Version des règles :** 1.0  
**Dernière mise à jour :** 29/09/2025  
**Auteur :** Équipe WindFlow
