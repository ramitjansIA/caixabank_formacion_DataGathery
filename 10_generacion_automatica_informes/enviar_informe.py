"""Prepara un correo con el informe adjunto y permite enviarlo por SMTP."""
import argparse
import mimetypes
import os
import smtplib
import ssl
from email.message import EmailMessage
from email.policy import SMTP
from pathlib import Path


def preparar(informe, remitente, destinatario, periodo):
    mensaje = EmailMessage(policy=SMTP)
    mensaje["From"] = remitente
    mensaje["To"] = destinatario
    mensaje["Subject"] = f"Observatorio · Informe documental · {periodo}"
    mensaje.set_content(
        f"Adjunto el informe documental del periodo {periodo}.\n"
        "Ábrelo en el navegador para consultar los indicadores y el detalle.\n"
    )
    tipo, _ = mimetypes.guess_type(informe.name)
    principal, subtipo = (tipo or "application/octet-stream").split("/", 1)
    mensaje.add_attachment(informe.read_bytes(), maintype=principal,
                           subtype=subtipo, filename=informe.name)
    return mensaje


def enviar(mensaje, remitente, destinatario):
    host = os.environ["SMTP_HOST"]
    puerto = int(os.environ["SMTP_PORT"])
    usuario = os.environ["SMTP_USER"]
    clave = os.environ["SMTP_PASSWORD"]
    modo = os.environ["SMTP_TLS"]
    contexto = ssl.create_default_context()
    if modo == "ssl":
        cliente = smtplib.SMTP_SSL(host, puerto, timeout=20, context=contexto)
    elif modo == "starttls":
        cliente = smtplib.SMTP(host, puerto, timeout=20)
    else:
        raise ValueError("SMTP_TLS debe ser ssl o starttls")

    with cliente:
        if modo == "starttls":
            cliente.ehlo()
            cliente.starttls(context=contexto)
            cliente.ehlo()
        cliente.login(usuario, clave)
        cliente.send_message(mensaje, from_addr=remitente, to_addrs=[destinatario])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("informe", type=Path)
    parser.add_argument("--de", required=True)
    parser.add_argument("--para", required=True)
    parser.add_argument("--periodo", required=True)
    accion = parser.add_mutually_exclusive_group(required=True)
    accion.add_argument("--borrador", type=Path)
    accion.add_argument("--enviar", action="store_true")
    args = parser.parse_args()
    mensaje = preparar(args.informe, args.de, args.para, args.periodo)
    if args.borrador is not None:
        with args.borrador.open("xb") as archivo:
            archivo.write(mensaje.as_bytes())
    else:
        enviar(mensaje, args.de, args.para)
        print("El servidor SMTP ha aceptado el mensaje.")


if __name__ == "__main__":
    main()
