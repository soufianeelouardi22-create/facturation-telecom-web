"""
pdf_web.py — Génération de facture PDF en mémoire (BytesIO) pour Flask.
Reproduit fidèlement le style de modules/pdf_generator.py.
"""

import io
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas
from reportlab.pdfbase.pdfmetrics import stringWidth


def _wrap(text, font, size, max_w):
    if not text:
        return []
    words = str(text).split()
    lines, cur = [], ''
    for w in words:
        test = (cur + ' ' + w).strip()
        if stringWidth(test, font, size) <= max_w:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def _fmt(val):
    """Formate un nombre en string avec espaces (style marocain)."""
    try:
        v = float(val)
    except (TypeError, ValueError):
        return '0.00'
    neg = v < 0
    s = f"{abs(v):,.2f}".replace(',', ' ')
    return ('-' + s) if neg else s


def generate_pdf(donnees: dict) -> bytes:
    """
    Génère une facture PDF à partir du dict donnees_json.
    Retourne les bytes du PDF.
    """
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    W, H = A4

    lh = 0.45 * cm  # line height standard

    # ── BLOC CLIENT (gauche) ────────────────────────────────────────
    cx, cy, cw, ch = 2*cm, H - 4.5*cm, 7.5*cm, 3*cm
    max_w = cw - 0.4*cm
    c.rect(cx, cy, cw, ch)

    lines_cli = []
    for l in _wrap(donnees.get('nom_magasin', ''), 'Helvetica-Bold', 9, max_w):
        lines_cli.append(('Helvetica-Bold', 9, l))
    adresse = donnees.get('adresse_magasin', '')
    ville   = donnees.get('ville_magasin', '')
    if ville and ville.upper() in adresse.upper():
        adresse = adresse.upper().replace(ville.upper(), '').strip(' ,')
    for l in _wrap(adresse, 'Helvetica', 8, max_w):
        lines_cli.append(('Helvetica', 8, l))
    if ville:
        lines_cli.append(('Helvetica-Bold', 8, ville))

    y0 = cy + (ch + len(lines_cli) * lh) / 2 - lh * 0.5
    for font, size, txt in lines_cli:
        c.setFont(font, size)
        c.drawCentredString(cx + cw / 2, y0, txt)
        y0 -= lh

    # ── BLOC SOCIÉTÉ ÉMETTRICE (droite) ─────────────────────────────
    sx, sy, sw, sh = W - 2*cm - 7.5*cm, H - 4.5*cm, 7.5*cm, 3*cm
    max_ws = sw - 0.4*cm
    c.rect(sx, sy, sw, sh)

    soc_info = donnees.get('societe_info') or {}
    if isinstance(soc_info, str):
        import json
        try:
            soc_info = json.loads(soc_info)
        except Exception:
            soc_info = {'nom': soc_info}

    lines_soc = [('Helvetica-Bold', 9, soc_info.get('nom', donnees.get('societe', '')))]
    for l in _wrap(soc_info.get('adresse', ''), 'Helvetica', 8, max_ws):
        lines_soc.append(('Helvetica', 8, l))
    if soc_info.get('ville'):
        lines_soc.append(('Helvetica-Bold', 8, soc_info['ville']))
    if soc_info.get('ice'):
        lines_soc.append(('Helvetica', 8, f"ICE : {soc_info['ice']}"))

    y0 = sy + (sh + len(lines_soc) * lh) / 2 - lh * 0.5
    for font, size, txt in lines_soc:
        c.setFont(font, size)
        c.drawCentredString(sx + sw / 2, y0, txt)
        y0 -= lh

    # ── TITRE ───────────────────────────────────────────────────────
    c.setFont('Helvetica-Bold', 12)
    c.drawCentredString(W / 2, H - 5.5*cm, f"Facture N°{donnees.get('numero_facture', '')}")
    c.setFont('Helvetica', 10)
    mois_nom = donnees.get('mois_nom', str(donnees.get('mois', '')))
    c.drawCentredString(W / 2, H - 6.3*cm,
                        f"COMMISSION CORRESPONDANTE AU MOIS : {mois_nom.lower()}")

    # ── CODE / DATE ─────────────────────────────────────────────────
    c.setFont('Helvetica', 10)
    c.drawString(2*cm, H - 7.3*cm, f"Code Magasin : {donnees.get('code', donnees.get('code_magasin', ''))}")
    c.drawRightString(W - 2*cm, H - 7.3*cm, f"Date : {donnees.get('date_facture', '')}")

    # ── TABLEAU LIGNES ───────────────────────────────────────────────
    y = H - 8.3*cm
    c.setFont('Helvetica-Bold', 10)
    c.rect(2*cm, y, W - 4*cm, 0.9*cm)
    c.drawString(2.2*cm, y + 0.25*cm, 'DESIGNATION')
    c.drawString(11*cm, y + 0.25*cm, 'QUANTITE')
    c.drawRightString(W - 2.2*cm, y + 0.25*cm, 'MONTANT')
    c.setFont('Helvetica', 10)

    y_start = y
    lignes = donnees.get('lignes') or []

    for ligne in lignes:
        y -= 0.7*cm
        desig = str(ligne.get('designation', ligne.get('description', '')))
        if len(desig) > 45:
            desig = desig[:42] + '...'
        c.drawString(2.2*cm, y + 0.18*cm, desig)

        qte = ligne.get('quantite', ligne.get('qte', ''))
        if qte and str(qte) != '-' and 'inscription' in desig.lower() and 'mobile' in desig.lower():
            c.drawString(11*cm, y + 0.18*cm, str(qte))

        montant = ligne.get('montant', ligne.get('total', ligne.get('amount', 0)))
        c.drawRightString(W - 2.2*cm, y + 0.18*cm, _fmt(montant))

    y -= 0.7*cm
    c.line(2*cm, y, W - 2*cm, y)
    y_fin = y

    # Lignes verticales
    c.line(2*cm,      y_start + 0.9*cm, 2*cm,      y_fin)
    c.line(10.5*cm,   y_start + 0.9*cm, 10.5*cm,   y_fin)
    c.line(13*cm,     y_start + 0.9*cm, 13*cm,      y_fin)
    c.line(W - 2*cm,  y_start + 0.9*cm, W - 2*cm,  y_fin)

    # ── TOTAUX (droite) ─────────────────────────────────────────────
    totals = [
        ('Montant HT',  float(donnees.get('montant_ht', 0) or 0)),
        ('TVA 20%',     float(donnees.get('tva', 0) or 0)),
        ('Montant TTC', float(donnees.get('ttc', 0) or 0)),
    ]
    ras = float(donnees.get('ras', 0) or 0)
    if ras:
        pct = donnees.get('pourcentage_tva_ras', 100)
        totals.append(('RAS', -ras))
        totals.append((f'TVA/RAS ({pct}%)', -float(donnees.get('tva_ras', 0) or 0)))
    totals.append(('NET A PAYER', float(donnees.get('net_a_payer', 0) or 0)))

    tw, tx = 8*cm, W - 2*cm - 8*cm
    yt = y - 0.3*cm
    c.setFont('Helvetica', 10)
    for label, valeur in totals:
        yt -= 0.6*cm
        c.rect(tx, yt, tw, 0.55*cm)
        c.drawCentredString(tx + tw / 4, yt + 0.15*cm, label)
        c.drawCentredString(tx + tw * 3 / 4, yt + 0.15*cm, _fmt(valeur))

    # ── MONTANT EN LETTRES ───────────────────────────────────────────
    y_arr = yt - 0.8*cm
    c.setFont('Helvetica', 10)
    c.drawString(2*cm, y_arr, "Arrêtée la Présente Facture à la somme de :")
    lettres = donnees.get('montant_lettres_complet') or donnees.get('montant_lettres', '')
    if not lettres:
        lettres = _montant_en_lettres(float(donnees.get('net_a_payer', 0) or 0))
    c.setFont('Helvetica-Oblique', 9)
    c.drawString(2*cm, y_arr - 0.6*cm, str(lettres))

    # ── SIGNATURE ───────────────────────────────────────────────────
    c.rect(2*cm, 2*cm, 5*cm, 2.2*cm)
    c.setFont('Helvetica', 9)
    c.drawCentredString(4.5*cm, 4*cm, 'Signature et cachet')

    # ── ÉCHÉANCE ────────────────────────────────────────────────────
    c.setFont('Helvetica', 10)
    c.drawRightString(W - 2*cm, 3.5*cm,
                      f"L'échéance de paiement Le : {donnees.get('date_echeance', '')}")

    # ── FOOTER ──────────────────────────────────────────────────────
    c.setFont('Helvetica', 8)
    infos = (f"RC : {donnees.get('rc', '')}  "
             f"IF : {donnees.get('if', donnees.get('if_num', ''))}  "
             f"Patente : {donnees.get('patente', '')}  "
             f"ICE : {donnees.get('ice_magasin', '')}")
    c.drawCentredString(W / 2, 1.2*cm, infos)

    c.save()
    return buf.getvalue()


def _montant_en_lettres(montant: float) -> str:
    """Fallback si montant_lettres_complet absent du JSON."""
    try:
        from num2words import num2words
        entier = int(montant)
        centimes = round((montant - entier) * 100)
        txt = num2words(entier, lang='fr').capitalize()
        if centimes:
            txt += f" et {num2words(centimes, lang='fr')} centimes"
        return txt + ' dirhams'
    except Exception:
        return f"{montant:.2f} dirhams"
