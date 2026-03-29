import os
import smtplib
from email.mime.text import MIMEText

from dotenv import load_dotenv

load_dotenv()

# Configuration SMTP
SMTP_SERVER: str = os.getenv("SMTP_SERVER", "localhost")
SMTP_PORT: int = int(os.getenv("SMTP_PORT", "25"))
SMTP_USE_TLS: bool = os.getenv("SMTP_USE_TLS", "false").lower() == "true"
SMTP_USE_SSL: bool = os.getenv("SMTP_USE_SSL", "false").lower() == "true"
SMTP_USER: str | None = os.getenv("SMTP_USER")
SMTP_PASSWORD: str | None = os.getenv("SMTP_PASSWORD")
EMAIL_FROM: str = os.getenv("EMAIL_FROM", "noreply@windflow.local")
VITE_BASE_URL: str = os.getenv("VITE_BASE_URL", "http://localhost:5173")


def send_email(to_email: str, subject: str, body: str, subtype: str = "plain"):
    """Méthode générique pour envoyer des emails"""

    # Création du message MIME
    msg = MIMEText(body, subtype)
    msg["Subject"] = subject
    msg["From"] = EMAIL_FROM
    msg["To"] = to_email

    try:
        # Choix de la classe de connexion en fonction de SSL
        server_class: type[smtplib.SMTP] = smtplib.SMTP_SSL if SMTP_USE_SSL else smtplib.SMTP

        with server_class(SMTP_SERVER, SMTP_PORT) as server:
            # Démarrage TLS si configuré (uniquement pour les connexions non-SSL)
            if SMTP_USE_TLS and not SMTP_USE_SSL:
                server.starttls()

            # Authentification si les identifiants sont fournis
            if SMTP_USER and SMTP_PASSWORD:
                server.login(SMTP_USER, SMTP_PASSWORD)

            # Envoi de l'email
            server.sendmail(EMAIL_FROM, [to_email], msg.as_string())
    except Exception as e:
        print(f"Erreur lors de l'envoi de l'email: {e}")


def send_reset_email(to_email: str, token: str):
    """Méthode pour envoyer un email de réinitialisation de mot de passe"""

    subject = "Réinitialisation de votre mot de passe"
    reset_link = f"{VITE_BASE_URL}/reset-password?token={token}"
    body = (
        f"Bonjour,\n\nPour réinitialiser votre mot de passe, "
        f"cliquez sur le lien suivant :\n{reset_link}\n\n"
        "Si vous n'avez pas fait cette demande, ignorez cet email."
    )
    send_email(to_email=to_email, subject=subject, body=body, subtype="plain")
