"""
Module de calculs - RAS, TVA, Primes, Dates
"""
import calendar
from datetime import datetime
from dateutil.relativedelta import relativedelta

class Calculations:
    
    @staticmethod
    def calculer_dates_facture(mois, annee):
        """
        Calcule date facture et date échéance
        - Date facture = dernier jour du mois
        - Date échéance = dernier jour du mois +4
        """
        # Date facture (dernier jour du mois)
        dernier_jour = calendar.monthrange(annee, mois)[1]
        date_facture = datetime(annee, mois, dernier_jour)
        
        # Date échéance (+4 mois, dernier jour)
        date_echeance_temp = date_facture + relativedelta(months=4)
        mois_echeance = date_echeance_temp.month
        annee_echeance = date_echeance_temp.year
        dernier_jour_echeance = calendar.monthrange(annee_echeance, mois_echeance)[1]
        date_echeance = datetime(annee_echeance, mois_echeance, dernier_jour_echeance)
        
        return {
            'date_facture': date_facture.strftime('%d/%m/%Y'),
            'date_echeance': date_echeance.strftime('%d/%m/%Y')
        }
    
    @staticmethod
    def generer_numero_facture(code, mois, annee):
        """Génère numéro facture: CODE-MM-AAAA"""
        return f"{code}-{mois:02d}-{annee}"
    
    @staticmethod
    def calculer_prime_activation(commission, type_indication):
        """
        Calcule prime d'activation selon type
        - Voix: 60%
        - Box/3G: 70%
        - Autre: 100%
        """
        type_lower = str(type_indication).lower()
        
        if 'voix' in type_lower:
            return commission * 0.60
        elif 'box' in type_lower or '3g' in type_lower:
            return commission * 0.70
        else:
            return commission
    
    @staticmethod
    def calculer_totaux(lignes_produits):
        """
        Calcule HT, TVA, TTC à partir des lignes produits
        lignes_produits = [{'designation': ..., 'montant': ...}, ...]
        """
        # Garder TOUTES les lignes (même montant = 0)
        lignes_valides = lignes_produits
        
        # Total HT (seulement lignes != 0)
        montant_ht = sum(l.get('montant', 0) for l in lignes_produits if l.get('montant', 0) != 0)
        
        # TVA 20%
        tva = montant_ht * 0.20
        
        # TTC
        ttc = montant_ht + tva
        
        return {
            'montant_ht': round(montant_ht, 2),
            'tva': round(tva, 2),
            'ttc': round(ttc, 2),
            'lignes_valides': lignes_valides  # Toutes les lignes, même 0
        }
    
    @staticmethod
    def calculer_ras_tva(montant_ht, tva, type_societe, avec_attestation):
        """
        Calcule RAS et TVA/RAS selon type société
        
        Société Morale: Pas de RAS
        Personne Physique sans attestation: TVA/RAS 100%
        Personne Physique avec attestation: TVA/RAS 75%
        """
        type_lower = str(type_societe).lower()
        attestation_lower = str(avec_attestation).lower()
        
        # Société morale - pas de RAS
        if 'moral' in type_lower:
            return {
                'ras': 0,
                'tva_ras': 0,
                'ras_applicable': False
            }
        
        # Personne physique
        ras = montant_ht * 0.10
        
        # Attestation ?
        if attestation_lower in ['oui', 'yes', '1', 'true']:
            # Avec attestation: 75%
            tva_ras = tva * 0.75
        else:
            # Sans attestation: 100%
            tva_ras = tva * 1.00
        
        return {
            'ras': round(ras, 2),
            'tva_ras': round(tva_ras, 2),
            'ras_applicable': True,
            'pourcentage_tva_ras': 75 if attestation_lower in ['oui', 'yes', '1', 'true'] else 100
        }
    
    @staticmethod
    def calculer_net_a_payer(ttc, ras, tva_ras):
        """Calcule NET À PAYER = TTC - RAS - TVA/RAS"""
        return round(ttc - ras - tva_ras, 2)
    
    @staticmethod
    def grouper_produits_par_code(donnees_excel):
        """
        Groupe les produits par code magasin
        Input: DataFrame ou liste de dict avec colonnes: design, montant, date, code
        Output: {code: [{'designation': ..., 'montant': ...}, ...]}
        """
        produits_par_code = {}
        
        for row in donnees_excel:
            code = str(row.get('CODE MAGASIN') or row.get('code') or row.get('Code'))
            designation = row.get('design') or row.get('designation')
            montant = float(row.get('SommeDeMontant') or row.get('montant') or 0)
            
            if code not in produits_par_code:
                produits_par_code[code] = []
            
            produits_par_code[code].append({
                'designation': designation,
                'montant': montant,
                'quantite': '-'
            })
        
        return produits_par_code
    
    @staticmethod
    def calculer_quantite_activations(activations_list, code):
        """
        Compte le nombre d'activations pour un code
        """
        return len([a for a in activations_list if str(a.get('code')) == str(code)])
    
    @staticmethod
    def calculer_prime_activations_totale(activations_list, code):
        """
        Calcule la prime totale d'activations pour un code
        en appliquant les coefficients 60%/70%
        """
        activations_code = [a for a in activations_list if str(a.get('code')) == str(code)]
        
        prime_totale = 0
        details = []
        
        for act in activations_code:
            commission = float(act.get('commission') or 0)
            type_indication = act.get('type_indication', '')
            
            prime = Calculations.calculer_prime_activation(commission, type_indication)
            prime_totale += prime
            
            details.append({
                'numero_tel': act.get('numero_tel'),
                'date': act.get('date_activation'),
                'plan': act.get('plan_tarifaire'),
                'type': 'Voix' if 'voix' in str(type_indication).lower() else 'Box',
                'commission_brute': commission,
                'prime': prime
            })
        
        return {
            'prime_totale': round(prime_totale, 2),
            'quantite': len(activations_code),
            'details': details
        }
    
    @staticmethod
    def extraire_mois_annee(date_str):
        """
        Extrait mois et année d'une date
        Format attendu: '01/09/2025' ou '2025-09-01'
        """
        try:
            # Essayer format dd/mm/yyyy
            if '/' in date_str:
                parts = date_str.split('/')
                if len(parts) == 3:
                    return int(parts[1]), int(parts[2])
            
            # Essayer format yyyy-mm-dd
            elif '-' in date_str:
                parts = date_str.split('-')
                if len(parts) == 3:
                    return int(parts[1]), int(parts[0])
            
            return None, None
        except:
            return None, None
    
    @staticmethod
    def nom_mois(numero_mois):
        """Retourne le nom du mois en français (première lettre majuscule)"""
        mois = [
            "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
            "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"
        ]
        if 1 <= numero_mois <= 12:
            return mois[numero_mois - 1]
        return ""
    
    @staticmethod
    def montant_en_lettres(montant):
        """
        Convertit un montant en lettres (français)
        Simplifié - pour montants courants
        """
        # Cette fonction peut être étendue avec une bibliothèque comme num2words
        # Pour l'instant, retourne un placeholder
        entier = int(montant)
        decimales = int((montant - entier) * 100)
        
        # Placeholder simple
        return f"{montant:.2f} dirhams"