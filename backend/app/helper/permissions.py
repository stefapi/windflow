from datetime import datetime
from .croniter import croniter
import json

def is_in_cron_interval(test_dt, cron_start_expr, cron_end_expr):
    """
    Vérifie si une date est comprise dans l'intervalle défini par deux règles cron.

    :param test_dt: datetime - Date/heure à tester
    :param cron_start_expr: str - Règle cron pour le début
    :param cron_end_expr: str - Règle cron pour la fin
    :return: bool - True si test_dt est dans l'intervalle [début, fin[
    """
    # Trouver la dernière occurrence de début <= test_dt
    iter_start = croniter.croniter(cron_start_expr, test_dt)
    prev_start = iter_start.get_prev(datetime)
    next_start = iter_start.get_next(datetime)
    start_occurrence = prev_start if next_start != test_dt else test_dt

    # Trouver la prochaine occurrence de fin après le début trouvé
    iter_end = croniter.croniter(cron_end_expr, start_occurrence)
    end_occurrence = iter_end.get_next(datetime)

    # Vérifier l'intervalle [début, fin[
    return start_occurrence <= test_dt < end_occurrence

def is_rule_accessible_now(rule):
    """
    Vérifie si une règle est accessible au moment actuel en fonction de son access_schedule.

    :param rule: Rule - La règle à vérifier
    :return: bool - True si la règle est accessible maintenant, False sinon
    """
    # Si pas d'access_schedule défini, la règle est toujours accessible
    if not rule.access_schedule:
        return True

    try:
        # Parser le JSON de l'access_schedule
        if isinstance(rule.access_schedule, str):
            schedule = json.loads(rule.access_schedule)
        else:
            schedule = rule.access_schedule

        # Vérifier que les clés 'start' et 'end' sont présentes
        if 'start' not in schedule or 'end' not in schedule:
            return True  # Si le format n'est pas correct, on autorise l'accès

        # Vérifier si l'heure actuelle est dans l'intervalle
        current_time = datetime.now()
        return is_in_cron_interval(current_time, schedule['start'], schedule['end'])

    except (json.JSONDecodeError, KeyError, Exception):
        # En cas d'erreur de parsing ou autre, on autorise l'accès par défaut
        return True

def has_permission(db, user, target_env: int= None, target_element:int =None, permission: (str or list[str]) = None ) -> bool:
    """
    Vérifie si l'utilisateur possède la permission demandée dans l'environnement cible ou sur l'élément cible.

    Un utilisateur a la permission si :
      - Il est superadmin,
      - OU s'il appartient à une organisation et:
        - Il appartient à un groupe qui s'applique à cette organisation et à ce user: on retient les policy associées
        - Il a des policy qui s'appliquent à ce user: on retient ces policy

        Pour chaque policy retenue, on vérifie les règles associées:
        - Si la fonction est "admin", l'utilisateur a tous les droits
        - Sinon, on vérifie que la fonction correspond à la permission demandée et que l'environnement
          ou l'élément sur lequel s'applique la règle correspond à celui passé en paramètre

    Les règles peuvent s'appliquer soit:
    - à un environnement (si environment_id n'est pas None dans la rule)
    - à un élément (si element_id n'est pas None dans la rule)
    - à tous les environnements et tous les éléments si les deux sont None

    Par ailleurs:
    - si target_env est None on regardera les règles par rapport à target_element
    - si target_element est None on regardera les règles par rapport à target_env
    - si target_env et target_element sont None, on retournera faux sauf si les deux éléments des règles sont à None
    """
    # Si l'utilisateur est superadmin, il a tous les droits
    if user.is_superadmin:
        return True

    # Récupérer toutes les policies applicables à l'utilisateur
    applicable_policies = set()

    # Pour chaque organisation de l'utilisateur
    for organization in user.organizations:
        # Policies des groupes de l'utilisateur dans cette organisation
        for group in user.groups:
            if group.organization_id == organization.id:
                for policy in group.policies:
                    if policy.organization_id == organization.id:
                        applicable_policies.add(policy)

        # Policies directement associées à l'utilisateur
        for policy in user.policies:
            if policy.organization_id == organization.id:
                applicable_policies.add(policy)

    # Vérifier les règles de chaque policy applicable
    for policy in applicable_policies:
        for rule in policy.rules:
            # Vérifier que la fonction correspond à la permission demandée
            if isinstance(permission, list):
                check = any( str.lower(perm) == rule.function.name for perm in permission )
            elif permission is None:
                check = False
            else:
                check = str.lower(permission) == rule.function.name
            if check or rule.function.name == "admin":
                # Vérifier d'abord si la règle est accessible selon son horaire
                if not is_rule_accessible_now(rule):
                    continue  # Passer à la règle suivante si pas accessible maintenant

                # Cas où les deux sont None: la règle s'applique à tous les environnements et éléments
                if rule.environment_id is None and rule.element_id is None:
                    return True

                # Cas où target_env et target_element sont tous les deux None
                if target_env is None and target_element is None:
                    # On retourne True seulement si les deux éléments des règles sont à None
                    if rule.environment_id is None and rule.element_id is None:
                        return True

                # Cas où target_element est None: on vérifie par rapport à target_env
                elif target_element is None:
                    if rule.environment_id == target_env:
                        return True

                # Cas où target_env est None: on vérifie par rapport à target_element
                elif target_env is None:
                    if rule.element_id == target_element.id:
                        return True
                    if rule.environment_id == target_element.environment_id:
                        return True

                # Cas où les deux sont spécifiés
                else:
                    # Si la règle s'applique directement à l'élément
                    if rule.element_id == target_element.id:
                        return True
                    # Si la règle s'applique à l'environnement de l'élément ou à l'environnement cible
                    if rule.environment_id == target_element.environment_id or rule.environment_id == target_env:
                        return True

    return False
