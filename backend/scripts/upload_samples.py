"""Simula os custodiantes: envia os arquivos de exemplo para o S3, na ordem do manifesto.

Cada envio dispara uma mensagem na fila, e o worker faz o resto.
Uso:  AWS_ENDPOINT_URL=http://localhost:4566 python -m scripts.upload_samples
"""

from __future__ import annotations

import json
import time

from app.config import Settings
from app.infra.aws import aws_client


def main(delay_seconds: float = 0.3) -> None:
    s = Settings.from_env()
    s3 = aws_client("s3")
    manifest = json.loads((s.data_dir / "manifest.json").read_text())
    for item in manifest:
        # Prefixo com o horário: o reenvio corrigido de um arquivo não sobrescreve a versão anterior.
        stamp = item["received_at"].replace("-", "").replace(":", "")[:13]
        key = f"inbox/{stamp}/{item['delivered_as']}"
        s3.put_object(
            Bucket=s.bucket,
            Key=key,
            Body=(s.data_dir / item["path"]).read_bytes(),
            Metadata={"received-at": item["received_at"]},
        )
        print(f"enviado {key}")
        time.sleep(delay_seconds)  # espaça os envios para a fila receber na ordem
    print(f"{len(manifest)} arquivos enviados para s3://{s.bucket}/inbox/")


if __name__ == "__main__":
    main()
