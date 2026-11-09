"""Firma de los archivos que la app aplica (orden de Claudio, 1.1.33): precios.json y verified_photos.json.

Uso: python3 .github/firma/firmar.py precios.json verified_photos.json
Escribe <archivo>.sig al lado: firma ECDSA P-256 / SHA-256 (DER) de los bytes exactos del archivo, en base64.
La clave privada (PEM, PKCS#8) viene del secreto de GitHub Actions FIRMA_CLAVE_PRIVADA; nunca está en el repo.
La pública va dentro de la app (SignedFiles.kt). Sin el secreto, sale con aviso y código 0 (no firma).
"""
import base64, os, sys
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

pem = os.environ.get('FIRMA_CLAVE_PRIVADA', '').strip()
if not pem:
    print('::warning::Falta el secreto FIRMA_CLAVE_PRIVADA: no se firma (la app 1.1.33+ no aplicará el archivo).')
    sys.exit(0)
key = serialization.load_pem_private_key(pem.encode(), password=None)
pub = key.public_key()
for f in sys.argv[1:]:
    data = open(f, 'rb').read()
    sig = key.sign(data, ec.ECDSA(hashes.SHA256()))
    pub.verify(sig, data, ec.ECDSA(hashes.SHA256()))   # comprobación antes de publicar
    open(f + '.sig', 'w').write(base64.b64encode(sig).decode() + '\n')
    print('firmado', f, len(data), 'bytes')
