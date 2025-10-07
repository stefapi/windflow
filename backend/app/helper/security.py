import bcrypt
from ..core import auth

# Hashage
def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

# Vérification
def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())
    except (ValueError, bcrypt.exceptions.SaltValidationError):
        return False

# Création d'un token de réinitialisation de mot de passe
def create_password_reset_token(user_id: int) -> str:
    """
    Crée un token de réinitialisation de mot de passe pour un utilisateur.

    Args:
        user_id: L'ID de l'utilisateur pour lequel créer le token

    Returns:
        Le token de réinitialisation
    """
    return auth.create_token(data={"sub": str(user_id)}, token_type="password_reset")
