"""
Module de traitement des fichiers liquidation Orange
Version corrigée avec noms de colonnes exacts
"""
import pandas as pd
import openpyxl
from datetime import datetime
import json
import os

class LiquidationProcessor:
    
    def __init__(self):
        # Charger les coefficients
        self.charger_coefficients()
        
    def charger_coefficients(self):
        """Charge les coefficients depuis le fichier config"""
        try:
            with open('config/coefficients.json', 'r') as f:
                self.coefficients = json.load(f)
        except:
            # Valeurs par défaut
            self.coefficients = {
                "airtime_postpaye": 0.65,
                "activations_mobile_voix": 0.60,
                "activations_mobile_box": 0.70,
                "activations_fixe": 0.70,
                "prime_enseigne_mobile": 1.0,
                "prime_enseigne_fixe": 1.0,
                "prime_objectif_mobile": 1.0,
                "prime_objectif_fixe": 1.0,
                "prime_acces_fixe": 1.0,
                "penalite": 0.70
            }
    
    def lire_fichier_mobile(self, fichier_path):
        """Lit le fichier Mobile et extrait toutes les données nécessaires"""
        donnees = {
            'airtime_postpaye': self._extraire_airtime_mobile(fichier_path),  # Fonction spéciale
            'activations': self._extraire_activations_mobile(fichier_path, 'BD Activation'),
            'prime_objectif': self._extraire_prime_simple(fichier_path, 'Prime d\'objectif', 'prime objectif', 'CODE POS'),
            'prime_enseigne': self._extraire_prime_simple(fichier_path, 'Prime d\'enseigne', "Prime d'enseigne", 'CODE POS'),  # Corriger nom colonne
            'penalite': self._extraire_prime_simple_penalite_mobile(fichier_path, 'Retard Doc'),
        }
        
        return donnees
    
    def _extraire_airtime_mobile(self, fichier):
        """Extrait Airtime postpayé depuis fichier Mobile (format tableau pivot)"""
        try:
            # Lire sans header car format spécial
            df = pd.read_excel(fichier, header=None)
            
            # Trouver ligne header (contient 'Airtime')
            header_row = None
            for idx, row in df.iterrows():
                if any('Airtime' in str(val) for val in row.values if pd.notna(val)):
                    header_row = idx
                    break
            
            if header_row is None:
                print("WARNING: Pas de header Airtime trouvé dans fichier Mobile")
                return {}
            
            # Définir header et lire données
            df.columns = df.iloc[header_row].values
            df = df.iloc[header_row + 1:].reset_index(drop=True)
            
            # Trouver colonnes code et airtime
            code_col = df.columns[0]  # Première colonne = codes
            airtime_col = None
            for col in df.columns:
                if 'Airtime' in str(col):
                    airtime_col = col
                    break
            
            if airtime_col is None:
                print("WARNING: Colonne Airtime non trouvée")
                return {}
            
            # Extraire données
            resultats = {}
            for _, row in df.iterrows():
                code = str(row[code_col]).strip()
                if code and code != 'nan' and code != 'Total':
                    try:
                        airtime_val = float(row[airtime_col]) if pd.notna(row[airtime_col]) else 0
                        if airtime_val > 0:
                            coef = self.coefficients['airtime_postpaye']
                            resultats[code] = {
                                'montant_brut': airtime_val,
                                'coefficient': coef,
                                'montant_calcule': airtime_val * coef
                            }
                    except:
                        continue
            
            print(f"DEBUG: Airtime Mobile extrait pour {len(resultats)} codes")
            return resultats
            
        except Exception as e:
            print(f"Erreur extraction airtime mobile: {e}")
            import traceback
            traceback.print_exc()
            return {}
    
    def lire_fichier_darbox(self, fichier_path):
        """Lit le fichier DarBox"""
        donnees = {
            'activations': self._extraire_activations_mobile(fichier_path, 'BD Activation'),
            'prime_objectif': self._extraire_prime_simple(fichier_path, 'Prime d\'objectif', 'prime objectif', 'CODE POS'),
            'prime_enseigne': self._extraire_prime_simple(fichier_path, 'Prime d\'enseigne', "Prime d'enseigne", 'CODE POS'),  # Corriger nom colonne
            'penalite': self._extraire_prime_simple_penalite_darbox(fichier_path, 'Retard Doc'),
        }
        
        return donnees
    
    def lire_fichier_fixe_b2b(self, fichier_path):
        """Lit le fichier Fixe B2B - EXTRACTION PRÉCISE"""
        
        print(f"DEBUG: Lecture Fixe B2B: {fichier_path}")
        
        # Activations (Comm Fixe Global)
        activations = self._extraire_fixe_b2b_activations(fichier_path)
        print(f"DEBUG: Activations extraites: {len(activations)} codes")
        
        # Prime d'enseigne
        prime_enseigne = self._extraire_fixe_b2b_prime_enseigne(fichier_path)
        print(f"DEBUG: Prime enseigne extraite: {len(prime_enseigne)} codes")
        
        # Prime d'objectif
        prime_objectif = self._extraire_fixe_b2b_prime_objectif(fichier_path)
        print(f"DEBUG: Prime objectif extraite: {len(prime_objectif)} codes")
        
        # Prime d'accès
        prime_acces = self._extraire_fixe_b2b_prime_acces(fichier_path)
        print(f"DEBUG: Prime accès extraite: {len(prime_acces)} codes")
        
        # Pénalités
        penalite = self._extraire_fixe_b2b_penalite(fichier_path)
        print(f"DEBUG: Pénalités extraites: {len(penalite)} codes")
        
        return {
            'activations': activations,
            'prime_enseigne': prime_enseigne,
            'prime_objectif': prime_objectif,
            'prime_acces': prime_acces,
            'penalite': penalite
        }
    
    def lire_fichier_fixe_b2c(self, fichier_path):
        """Lit le fichier Fixe B2C - EXTRACTION PRÉCISE"""
        
        # Activations
        activations = self._extraire_fixe_b2c_activations(fichier_path)
        
        # Prime objectif
        prime_objectif = self._extraire_fixe_b2c_prime_objectif(fichier_path)
        
        # Prime enseigne
        prime_enseigne = self._extraire_fixe_b2c_prime_enseigne(fichier_path)
        
        # Pénalités
        penalite = self._extraire_fixe_b2c_penalite(fichier_path)
        
        return {
            'activations': activations,
            'prime_objectif': prime_objectif,
            'prime_enseigne': prime_enseigne,
            'penalite': penalite
        }
    
    # === EXTRACTION MOBILE/DARBOX ===
    
    def _trouver_colonne_code(self, df, feuille_nom=''):
        """Helper: Trouve la colonne code dans un DataFrame
        
        Returns:
            str: Nom de la colonne code, ou None si non trouvée
        """
        # D'abord ESC3 (le plus courant)
        if 'ESC3' in df.columns:
            return 'ESC3'
        
        # Pour feuilles Niv, chercher aussi CODE
        if 'Niv' in feuille_nom:
            for col in df.columns:
                if 'CODE' in col:
                    return col
        
        # Chercher CODE POS
        for col in df.columns:
            if 'CODE' in col.upper() and 'POS' in col.upper():
                return col
        
        # Chercher toute colonne avec CODE
        for col in df.columns:
            if 'CODE' in col.upper():
                return col
        
        return None
    
    # === EXTRACTION MOBILE/DARBOX ===
    
    def _extraire_airtime(self, fichier, feuille):
        """Extrait Airtime postpayé"""
        try:
            df = pd.read_excel(fichier, sheet_name=feuille)
            
            # Chercher colonne code
            code_col = None
            for col in df.columns:
                if 'CODE' in col.upper() and 'POS' in col.upper():
                    code_col = col
                    break
            
            if not code_col:
                return {}
            
            resultats = {}
            for code, group in df.groupby(code_col):
                total = group['Airtime'].sum() if 'Airtime' in group.columns else 0
                resultats[str(code)] = {
                    'montant_brut': total,
                    'coefficient': self.coefficients['airtime_postpaye'],
                    'montant_calcule': total * self.coefficients['airtime_postpaye']
                }
            
            return resultats
        except Exception as e:
            print(f"Erreur extraction airtime: {e}")
            return {}
    
    def _extraire_activations_mobile(self, fichier, feuille):
        """Extrait les activations Mobile/DarBox"""
        try:
            # Essayer plusieurs variantes du nom
            df = None
            variantes = [feuille, 'BD Activation', 'Bd Activation', 'bd activation']
            for nom in variantes:
                try:
                    df = pd.read_excel(fichier, sheet_name=nom)
                    break
                except:
                    continue
            
            if df is None:
                raise Exception(f"Worksheet named '{feuille}' not found")
            
            # Chercher colonne code
            code_col = None
            for col in df.columns:
                if 'CODE' in col.upper() and 'POS' in col.upper():
                    code_col = col
                    break
            
            if not code_col:
                return {}
            
            resultats = {}
            for code, group in df.groupby(code_col):
                activations = []
                for _, row in group.iterrows():
                    indicateur = str(row.get('Indicateur VOIX/3G', '')).upper()
                    
                    # Chercher colonne commission
                    commission = 0
                    for col in group.columns:
                        if 'commission' in col.lower() and 'activation' in col.lower():
                            commission = float(row.get(col, 0))
                            break
                    
                    # Coefficient selon type
                    if 'BOX' in indicateur:
                        coef = self.coefficients['activations_mobile_box']
                    else:  # VOIX
                        coef = self.coefficients['activations_mobile_voix']
                    
                    activations.append({
                        'numero_tel': row.get('N° Tel', ''),
                        'date_activation': row.get('Date Activation', ''),
                        'plan_tarifaire': row.get('Plan Tarifaire', ''),
                        'type': indicateur,
                        'commission_brute': commission,
                        'coefficient': coef,
                        'prime': commission * coef,
                        'nom_client': row.get('Nom Titulaire du Client', ''),
                        'type_segment': row.get('Type de segment', row.get('Type de Segment', 'Residential'))
                    })
                
                # Prime d'accès = somme colonne "Prime d'accès" du groupe
                prime_acces = 0
                for col in df.columns:
                    if "prime" in col.lower() and "acc" in col.lower():
                        prime_acces = group[col].sum() if pd.notna(group[col].sum()) else 0
                        break

                resultats[str(code)] = {
                    'quantite': len(activations),
                    'activations': activations,
                    'prime_totale': sum(a['prime'] for a in activations),
                    'prime_acces': prime_acces
                }
            
            return resultats
        except Exception as e:
            print(f"Erreur extraction activations: {e}")
            return {}
    
    def _extraire_prime_simple(self, fichier, feuille, colonne_montant, code_col_cherche):
        """Extrait une prime simple"""
        try:
            df = pd.read_excel(fichier, sheet_name=feuille)
            
            # Chercher colonne code
            code_col = None
            for col in df.columns:
                if code_col_cherche.upper() in col.upper():
                    code_col = col
                    break
            
            if not code_col:
                return {}
            
            resultats = {}
            for code, group in df.groupby(code_col):
                if colonne_montant and colonne_montant in group.columns:
                    total = group[colonne_montant].sum()
                else:
                    # Chercher une colonne de montant
                    montant_cols = [c for c in group.columns if 'montant' in c.lower() or 'prime' in c.lower()]
                    total = group[montant_cols[0]].sum() if montant_cols else 0
                
                resultats[str(code)] = {
                    'montant_brut': total,
                    'coefficient': 1.0,
                    'montant_calcule': total
                }
            
            return resultats
        except Exception as e:
            print(f"Erreur extraction prime simple ({feuille}): {e}")
            return {}
    
    # === EXTRACTION FIXE B2B - AVEC NOMS EXACTS ===
    

    def _extraire_prime_simple_penalite_mobile(self, fichier, feuille):
        """Extrait pénalité retard doc Mobile - NOM EXACT"""
        try:
            df = pd.read_excel(fichier, sheet_name=feuille)
            
            # Chercher colonne code
            code_col = None
            for col in df.columns:
                if 'CODE' in col.upper() and 'POS' in col.upper():
                    code_col = col
                    break
            
            if not code_col:
                print(f"DEBUG: Colonne code non trouvée dans {feuille}")
                return {}
            
            # Nom EXACT de la colonne
            montant_col = "Penalité commission d'activation"
            if montant_col not in df.columns:
                print(f"DEBUG: Colonne '{montant_col}' non trouvée dans Mobile {feuille}")
                return {}
            
            resultats = {}
            for code, group in df.groupby(code_col):
                total = group[montant_col].sum()
                resultats[str(code)] = {
                    'montant_brut': total,
                    'coefficient': 1.0,
                    'montant_calcule': total
                }
                print(f"DEBUG: Pénalité retard doc Mobile - Code {code}: {total:.2f}")
            
            return resultats
        except Exception as e:
            print(f"Erreur extraction pénalité Mobile: {e}")
            return {}
    
    def _extraire_prime_simple_penalite_darbox(self, fichier, feuille):
        """Extrait pénalité retard doc DarBox - NOM EXACT"""
        try:
            df = pd.read_excel(fichier, sheet_name=feuille)
            
            # Chercher colonne code
            code_col = None
            for col in df.columns:
                if 'CODE' in col.upper() and 'POS' in col.upper():
                    code_col = col
                    break
            
            if not code_col:
                print(f"DEBUG: Colonne code non trouvée dans {feuille}")
                return {}
            
            # Nom EXACT de la colonne (avec faute d'orthographe)
            montant_col = "Pénalité comm acitvation"
            if montant_col not in df.columns:
                print(f"DEBUG: Colonne '{montant_col}' non trouvée dans DarBox {feuille}")
                return {}
            
            resultats = {}
            for code, group in df.groupby(code_col):
                total = group[montant_col].sum()
                resultats[str(code)] = {
                    'montant_brut': total,
                    'coefficient': 1.0,
                    'montant_calcule': total
                }
                print(f"DEBUG: Pénalité retard doc DarBox - Code {code}: {total:.2f}")
            
            return resultats
        except Exception as e:
            print(f"Erreur extraction pénalité DarBox: {e}")
            return {}
    
    def _extraire_fixe_b2b_activations(self, fichier):
        """Extrait activations Fixe B2B (4 feuilles spécifiques)"""
        resultats = {}
        
        feuilles_config = [
            ('Niv 1', 'CODE', 'com activation'),
            ('PARTAGE FTTH', 'ESC3', 'com activation'),
            ('Business box 4G', 'ESC3', 'com activation'),
            ('ADSL', 'ESC3', 'com activation')
        ]
        
        for feuille_nom, code_cherche, montant_col in feuilles_config:
            try:
                # Essayer avec et sans espace final
                df = None
                for nom_essai in [feuille_nom, feuille_nom + ' ']:
                    try:
                        df = pd.read_excel(fichier, sheet_name=nom_essai)
                        break
                    except:
                        continue
                
                if df is None:
                    print(f"DEBUG: Feuille {feuille_nom} non trouvée")
                    continue
                
                # Chercher colonne code
                code_col = None
                for col in df.columns:
                    if code_cherche in col:
                        code_col = col
                        break
                
                if not code_col:
                    print(f"DEBUG: Colonne code non trouvée dans {feuille_nom}")
                    continue
                
                # Chercher colonne montant
                montant_col_reel = None
                for col in df.columns:
                    if montant_col in col.lower():
                        montant_col_reel = col
                        break
                
                if not montant_col_reel:
                    print(f"DEBUG: Colonne {montant_col} non trouvée dans {feuille_nom}")
                    continue
                
                for code, group in df.groupby(code_col):
                    code_str = str(int(code)) if pd.notna(code) and code != '' else str(code)
                    
                    if code_str not in resultats:
                        resultats[code_str] = {'montant_brut': 0}
                    
                    resultats[code_str]['montant_brut'] += group[montant_col_reel].sum()
                    print(f"DEBUG: {feuille_nom} - Code {code_str}: +{group[montant_col_reel].sum():.2f}")
            
            except Exception as e:
                print(f"DEBUG: Erreur feuille {feuille_nom}: {e}")
                continue
        
        # Appliquer coefficient
        coef = self.coefficients['activations_fixe']
        for code in resultats:
            resultats[code]['coefficient'] = coef
            resultats[code]['montant_calcule'] = resultats[code]['montant_brut'] * coef
        
        return resultats
    
    def _extraire_fixe_b2b_prime_enseigne(self, fichier):
        """Extrait Prime d'enseigne depuis les feuilles - NOM EXACT"""
        resultats = {}
        
        feuilles = ['Niv 1', 'PARTAGE FTTH', 'Business box 4G', 'ADSL']
        
        for feuille_nom in feuilles:
            try:
                # Essayer avec et sans espace
                df = None
                for nom_essai in [feuille_nom, feuille_nom + ' ']:
                    try:
                        df = pd.read_excel(fichier, sheet_name=nom_essai)
                        break
                    except:
                        continue
                
                if df is None:
                    continue
                
                # Chercher colonne code
                code_col = None
                if 'Niv' in feuille_nom:
                    # Chercher ESC3 d'abord (colonnes codes dans Niv)
                    if 'ESC3' in df.columns:
                        code_col = 'ESC3'
                    else:
                        for col in df.columns:
                            if 'CODE' in col:
                                code_col = col
                                break
                else:
                    for col in df.columns:
                        if 'ESC3' in col:
                            code_col = col
                            break
                
                if not code_col:
                    print(f"DEBUG: Code non trouvé dans {feuille_nom} pour prime enseigne")
                    continue
                
                # Chercher colonne "Prime d'enseigne" EXACTEMENT
                enseigne_col = None
                if "Prime d'enseigne" in df.columns:
                    enseigne_col = "Prime d'enseigne"
                
                if enseigne_col:
                    for code, group in df.groupby(code_col):
                        code_str = str(int(code)) if pd.notna(code) and code != '' else str(code)
                        
                        if code_str not in resultats:
                            resultats[code_str] = {'montant_brut': 0}
                        
                        montant = group[enseigne_col].sum()
                        resultats[code_str]['montant_brut'] += montant
                        print(f"DEBUG: Prime enseigne {feuille_nom} - Code {code_str}: +{montant:.2f}")
                else:
                    print(f"DEBUG: Colonne 'Prime d'enseigne' non trouvée dans {feuille_nom}")
            
            except Exception as e:
                print(f"DEBUG: Erreur prime enseigne {feuille_nom}: {e}")
                continue
        
        # Appliquer coefficient
        coef = self.coefficients['prime_enseigne_fixe']
        for code in resultats:
            resultats[code]['coefficient'] = coef
            resultats[code]['montant_calcule'] = resultats[code]['montant_brut'] * coef
        
        return resultats
    
    def _extraire_fixe_b2b_prime_objectif(self, fichier):
        """Extrait Prime d'objectif - NOM EXACT + feuilles P OBJ"""
        resultats = {}
        
        # Feuilles normales
        feuilles_normales = ['Niv 1', 'PARTAGE FTTH', 'Business box 4G', 'ADSL']
        
        for feuille_nom in feuilles_normales:
            try:
                df = None
                for nom_essai in [feuille_nom, feuille_nom + ' ']:
                    try:
                        df = pd.read_excel(fichier, sheet_name=nom_essai)
                        break
                    except:
                        continue
                
                if df is None:
                    continue
                
                # Chercher colonne code
                code_col = None
                if 'Niv' in feuille_nom:
                    # Chercher ESC3 d'abord (colonnes codes dans Niv)
                    if 'ESC3' in df.columns:
                        code_col = 'ESC3'
                    else:
                        for col in df.columns:
                            if 'CODE' in col:
                                code_col = col
                                break
                else:
                    for col in df.columns:
                        if 'ESC3' in col:
                            code_col = col
                            break
                
                if not code_col:
                    continue
                
                # Chercher colonne objectif (insensible casse, prime/primes)
                objectif_col = None
                for col in df.columns:
                    col_lower = col.lower().strip()
                    if 'objectif' in col_lower and ('prime' in col_lower or 'primes' in col_lower):
                        objectif_col = col
                        break
                
                if objectif_col:
                    for code, group in df.groupby(code_col):
                        code_str = str(int(code)) if pd.notna(code) and code != '' else str(code)
                        
                        if code_str not in resultats:
                            resultats[code_str] = {'montant_brut': 0}
                        
                        montant = group[objectif_col].sum()
                        resultats[code_str]['montant_brut'] += montant
                        print(f"DEBUG: Prime objectif {feuille_nom} - Code {code_str}: +{montant:.2f}")
            
            except Exception as e:
                print(f"DEBUG: Erreur prime objectif {feuille_nom}: {e}")
                continue
        
        # Feuilles P OBJ spéciales
        feuilles_pobj = ['P OBJ 1ERE FACT BOX', 'P OBJ 1ERE FACT 4G']
        
        for feuille_nom in feuilles_pobj:
            try:
                df = pd.read_excel(fichier, sheet_name=feuille_nom)
                
                # Chercher colonne code ESC3 spécifiquement
                code_col = None
                if 'ESC3' in df.columns:
                    code_col = 'ESC3'
                else:
                    for col in df.columns:
                        if 'CODE' in col.upper() and 'POS' in col.upper():
                            code_col = col
                            break
                
                if not code_col:
                    continue
                
                # Chercher colonne montant
                montant_col = None
                for col in df.columns:
                    if 'prime' in col.lower() or 'objectif' in col.lower() or 'montant' in col.lower():
                        montant_col = col
                        break
                
                if montant_col:
                    for code, group in df.groupby(code_col):
                        code_str = str(int(code)) if pd.notna(code) and code != '' else str(code)
                        
                        if code_str not in resultats:
                            resultats[code_str] = {'montant_brut': 0}
                        
                        montant = group[montant_col].sum()
                        resultats[code_str]['montant_brut'] += montant
                        print(f"DEBUG: {feuille_nom} - Code {code_str}: +{montant:.2f}")
            
            except Exception as e:
                print(f"DEBUG: Erreur feuille {feuille_nom}: {e}")
                continue
        
        # Appliquer coefficient
        coef = self.coefficients['prime_objectif_fixe']
        for code in resultats:
            resultats[code]['coefficient'] = coef
            resultats[code]['montant_calcule'] = resultats[code]['montant_brut'] * coef
        
        return resultats
    
    def _extraire_fixe_b2b_prime_acces(self, fichier):
        """Extrait Prime d'accès - NOM EXACT"""
        resultats = {}
        
        feuilles = ['Niv 1', 'Business box 4G', 'ADSL']
        
        for feuille_nom in feuilles:
            try:
                df = None
                for nom_essai in [feuille_nom, feuille_nom + ' ']:
                    try:
                        df = pd.read_excel(fichier, sheet_name=nom_essai)
                        break
                    except:
                        continue
                
                if df is None:
                    continue
                
                # Chercher colonne code
                code_col = None
                if 'Niv' in feuille_nom:
                    # Chercher ESC3 d'abord (colonnes codes dans Niv)
                    if 'ESC3' in df.columns:
                        code_col = 'ESC3'
                    else:
                        for col in df.columns:
                            if 'CODE' in col:
                                code_col = col
                                break
                else:
                    for col in df.columns:
                        if 'ESC3' in col:
                            code_col = col
                            break
                
                if not code_col:
                    continue
                
                # Chercher "prime d'accès" ou "Prime d'accès" ou "Prime d'accés ADSL"
                acces_col = None
                if "prime d'accès" in df.columns:
                    acces_col = "prime d'accès"
                elif "Prime d'accès" in df.columns:
                    acces_col = "Prime d'accès"
                elif "Prime d'accés ADSL" in df.columns:
                    acces_col = "Prime d'accés ADSL"
                
                if acces_col:
                    for code, group in df.groupby(code_col):
                        code_str = str(int(code)) if pd.notna(code) and code != '' else str(code)
                        
                        if code_str not in resultats:
                            resultats[code_str] = {'montant_brut': 0}
                        
                        montant = group[acces_col].sum()
                        resultats[code_str]['montant_brut'] += montant
                        print(f"DEBUG: Prime accès {feuille_nom} - Code {code_str}: +{montant:.2f}")
                else:
                    print(f"DEBUG: Colonne PA non trouvée dans {feuille_nom}")
            
            except Exception as e:
                print(f"DEBUG: Erreur prime accès {feuille_nom}: {e}")
                continue
        
        # Appliquer coefficient
        coef = self.coefficients['prime_acces_fixe']
        for code in resultats:
            resultats[code]['coefficient'] = coef
            resultats[code]['montant_calcule'] = resultats[code]['montant_brut'] * coef
        
        return resultats
    
    def _extraire_fixe_b2b_penalite(self, fichier):
        """Extrait pénalités Fixe B2B"""
        resultats = {}
        
        try:
            wb = openpyxl.load_workbook(fichier, read_only=True)
            feuilles_penalite = [s for s in wb.sheetnames if 'RETARD DOC' in s.upper()]
            wb.close()
            
            for feuille_nom in feuilles_penalite:
                df = pd.read_excel(fichier, sheet_name=feuille_nom)
                
                code_col = None
                for col in df.columns:
                    if 'CODE' in col.upper() or 'ESC' in col.upper():
                        code_col = col
                        break
                
                if not code_col:
                    continue
                
                montant_col = None
                for col in df.columns:
                    if 'montant' in col.lower() or 'penalite' in col.lower():
                        montant_col = col
                        break
                
                if montant_col:
                    for code, group in df.groupby(code_col):
                        code_str = str(int(code)) if pd.notna(code) and code != '' else str(code)
                        
                        if code_str not in resultats:
                            resultats[code_str] = {'montant_brut': 0}
                        
                        resultats[code_str]['montant_brut'] += group[montant_col].sum()
        
        except Exception as e:
            print(f"Erreur pénalités B2B: {e}")
        
        return resultats
    
    # === EXTRACTION FIXE B2C ===
    
    def _extraire_fixe_b2c_activations(self, fichier):
        """Extrait activations Fixe B2C"""
        resultats = {}
        
        feuilles_config = [
            ('FIBRE B2C', 'ESC3', 'Montant commission en dh ht'),
            ('ADSL', 'ESC3', 'Commission pour activation')
        ]
        
        for feuille_nom, code_col, montant_col in feuilles_config:
            try:
                df = pd.read_excel(fichier, sheet_name=feuille_nom)
                
                if code_col not in df.columns:
                    continue
                
                if montant_col not in df.columns:
                    continue
                
                for code, group in df.groupby(code_col):
                    code_str = str(int(code)) if pd.notna(code) and code != '' else str(code)
                    
                    if code_str not in resultats:
                        resultats[code_str] = {'montant_brut': 0}
                    
                    resultats[code_str]['montant_brut'] += group[montant_col].sum()
            
            except Exception as e:
                print(f"Erreur activations B2C {feuille_nom}: {e}")
                continue
        
        # Appliquer coefficient
        coef = self.coefficients['activations_fixe']
        for code in resultats:
            resultats[code]['coefficient'] = coef
            resultats[code]['montant_calcule'] = resultats[code]['montant_brut'] * coef
        
        return resultats
    
    def _extraire_fixe_b2c_prime_objectif(self, fichier):
        """Extrait Prime d'objectif B2C depuis feuilles FIBRE B2C et ADSL"""
        resultats = {}
        
        feuilles = ['FIBRE B2C', 'ADSL']
        
        for feuille_nom in feuilles:
            try:
                df = None
                for nom_essai in [feuille_nom, feuille_nom + ' ', feuille_nom.lower()]:
                    try:
                        df = pd.read_excel(fichier, sheet_name=nom_essai)
                        break
                    except:
                        continue
                
                if df is None:
                    continue
                
                code_col = 'ESC3' if 'ESC3' in df.columns else None
                if not code_col:
                    for col in df.columns:
                        if 'CODE' in col.upper() or 'ESC' in col.upper():
                            code_col = col
                            break
                
                if not code_col:
                    continue
                
                montant_col = None
                for col in df.columns:
                    col_lower = col.lower().strip()
                    if 'objectif' in col_lower and ('prime' in col_lower or 'primes' in col_lower):
                        montant_col = col
                        break
                
                if not montant_col:
                    print(f"DEBUG B2C objectif: colonne introuvable dans {feuille_nom}, colonnes: {list(df.columns)}")
                    continue
                
                print(f"DEBUG B2C objectif {feuille_nom}: colonne='{montant_col}'")
                
                for code, group in df.groupby(code_col):
                    code_str = str(int(code)) if pd.notna(code) and code != '' else str(code)
                    
                    if code_str not in resultats:
                        resultats[code_str] = {'montant_brut': 0}
                    
                    montant = group[montant_col].sum()
                    resultats[code_str]['montant_brut'] += montant
            
            except Exception as e:
                print(f"Erreur prime objectif B2C {feuille_nom}: {e}")
                import traceback
                traceback.print_exc()
        
        # Appliquer coefficient
        coef = self.coefficients['prime_objectif_fixe']
        for code in resultats:
            resultats[code]['coefficient'] = coef
            resultats[code]['montant_calcule'] = resultats[code]['montant_brut'] * coef
        
        return resultats
    
    def _extraire_fixe_b2c_prime_enseigne(self, fichier):
        """Extrait Prime d'enseigne B2C"""
        resultats = {}
        
        feuilles = ['FIBRE B2C', 'ADSL']
        
        for feuille_nom in feuilles:
            try:
                df = pd.read_excel(fichier, sheet_name=feuille_nom)
                
                code_col = 'ESC3' if 'ESC3' in df.columns else None
                if not code_col:
                    continue
                
                # Chercher colonne prime enseigne
                enseigne_col = None
                for col in df.columns:
                    if 'enseigne' in col.lower():
                        enseigne_col = col
                        break
                
                if enseigne_col:
                    for code, group in df.groupby(code_col):
                        code_str = str(int(code)) if pd.notna(code) and code != '' else str(code)
                        
                        if code_str not in resultats:
                            resultats[code_str] = {'montant_brut': 0}
                        
                        resultats[code_str]['montant_brut'] += group[enseigne_col].sum()
            
            except Exception as e:
                print(f"Erreur prime enseigne B2C {feuille_nom}: {e}")
                continue
        
        # Appliquer coefficient
        coef = self.coefficients['prime_enseigne_fixe']
        for code in resultats:
            resultats[code]['coefficient'] = coef
            resultats[code]['montant_calcule'] = resultats[code]['montant_brut'] * coef
        
        return resultats
    
    def _extraire_fixe_b2c_penalite(self, fichier):
        """Extrait pénalités Fixe B2C (Résiliation) - NOMS EXACTS"""
        resultats = {}
        
        # Pénalité Fibre
        try:
            df = pd.read_excel(fichier, sheet_name='Pénalité Fibre')
            
            code_col = 'ESC3' if 'ESC3' in df.columns else None
            if not code_col:
                for col in df.columns:
                    if 'CODE' in col.upper() or 'ESC' in col.upper():
                        code_col = col
                        break
            
            if code_col and "Clawback commission d'activation" in df.columns:
                for code, group in df.groupby(code_col):
                    code_str = str(int(code)) if pd.notna(code) and code != '' else str(code)
                    
                    if code_str not in resultats:
                        resultats[code_str] = {'montant_brut': 0}
                    
                    montant = group["Clawback commission d'activation"].sum()
                    resultats[code_str]['montant_brut'] += montant
                    print(f"DEBUG: Pénalité résiliation Fibre - Code {code_str}: +{montant:.2f}")
            else:
                print("DEBUG: Colonne 'Clawback commission d\'activation' non trouvée dans Pénalité Fibre")
        
        except Exception as e:
            print(f"DEBUG: Feuille 'Pénalité Fibre' non trouvée ou erreur: {e}")
        
        # Pénalité ADSL (peut ne pas exister)
        try:
            df = pd.read_excel(fichier, sheet_name='Pénalité ADSL')
            
            code_col = 'ESC3' if 'ESC3' in df.columns else None
            if not code_col:
                for col in df.columns:
                    if 'CODE' in col.upper() or 'ESC' in col.upper():
                        code_col = col
                        break
            
            if code_col and "montant penlaite" in df.columns:
                df[code_col] = pd.to_numeric(df[code_col], errors='coerce')
                df = df.dropna(subset=[code_col])
                for code, group in df.groupby(code_col):
                    code_str = str(int(code)) if pd.notna(code) and code != '' else str(code)
                    
                    if code_str not in resultats:
                        resultats[code_str] = {'montant_brut': 0}
                    
                    montant = group["montant penlaite"].sum()
                    resultats[code_str]['montant_brut'] += montant
                    print(f"DEBUG: Pénalité résiliation ADSL - Code {code_str}: +{montant:.2f}")
            else:
                print("DEBUG: Colonne 'montant penlaite' non trouvée dans Pénalité ADSL")
        
        except Exception as e:
            print(f"DEBUG: Feuille 'Pénalité ADSL' non trouvée (normal si pas de pénalité ce mois): {e}")
        
        return resultats
    

    def calculer_etat_complet(self, mobile_data, darbox_data, fixe_b2b_data, fixe_b2c_data, db, societe=None):
        """Calcule l'état complet pour tous les codes FR
        
        Args:
            societe: 'BESTMARK' ou 'AFRINETWORKS' pour filtrer, ou None pour tous
        """
        etat = {}
        
        # Récupérer tous les codes FR uniquement
        codes_fr = self._get_codes_fr(db, societe)
        
        print(f"DEBUG: Calcul état pour {len(codes_fr)} codes FR (société: {societe})")
        
        for code in codes_fr:
            etat[code] = self._calculer_primes_code(
                code, mobile_data, darbox_data, fixe_b2b_data, fixe_b2c_data, db
            )
        
        return etat
    
    def _get_codes_fr(self, db, societe=None):
        """Récupère tous les codes FR depuis la base magasins (base globale)
        
        Args:
            societe: Filtre par société ('BESTMARK' ou 'AFRINETWORKS')
        """
        conn = db.get_connection()
        cursor = conn.cursor()
        
        # Récupérer TOUS les codes de la table magasins (base globale avec les FR)
        if societe:
            # Filtrer par société si spécifié
            cursor.execute('''
                SELECT code FROM magasins 
                WHERE societe = ?
            ''', (societe,))
        else:
            # Tous les codes FR
            cursor.execute('SELECT code FROM magasins')
        
        codes = [str(row[0]) for row in cursor.fetchall()]
        conn.close()
        
        return codes
    
    def _calculer_primes_code(self, code, mobile_data, darbox_data, fixe_b2b_data, fixe_b2c_data, db):
        """Calcule toutes les primes pour un code"""
        primes = {
            'code': code,
            'airtime_prepaye': 0,  # Vide - manuel
            'prime_inscription': 0,
            'qte_inscription': 0,
            'prime_acces': 0,
            'airtime_postpaye': 0,
            'prime_permanence_9': 0,  # Vide
            'prime_permanence_12': 0,  # Vide
            'prime_permanence_24': 0,  # Vide
            'prime_enseigne_mobile': 0,
            'prime_enseigne_fixe': 0,
            'prime_tpe': 0,  # Vide - manuel
            'comm_fixe_global': 0,
            'pa_fixe_global': 0,
            'support_commercial': 0,  # Vide - manuel
            'prime_portabilite': 0,  # Vide
            'prime_objectif_mobile': 0,
            'prime_objectif_fixe': 0,
            'kiosque': 0,  # Vide
            'penalite': 0,
        }
        
        # Airtime postpayé (Mobile uniquement)
        if code in mobile_data.get('airtime_postpaye', {}):
            primes['airtime_postpaye'] = mobile_data['airtime_postpaye'][code]['montant_calcule']
        
        # Prime inscription = Activations Mobile + DarBox
        mobile_act = mobile_data.get('activations', {}).get(code, {})
        darbox_act = darbox_data.get('activations', {}).get(code, {})
        
        primes['prime_inscription'] = mobile_act.get('prime_totale', 0) + darbox_act.get('prime_totale', 0)
        primes['qte_inscription'] = mobile_act.get('quantite', 0) + darbox_act.get('quantite', 0)
        
        # Prime d'accès mobile = extrait de BD Activation mobile
        coef_acces = self.coefficients.get('prime_acces_fixe', 1.0)
        primes['prime_acces'] = mobile_act.get('prime_acces', 0) * coef_acces
        
        # Prime enseigne mobile = Mobile + DarBox
        primes['prime_enseigne_mobile'] = (
            mobile_data.get('prime_enseigne', {}).get(code, {}).get('montant_calcule', 0) +
            darbox_data.get('prime_enseigne', {}).get(code, {}).get('montant_calcule', 0)
        )
        
        # Prime enseigne fixe = Fixe B2B + B2C
        primes['prime_enseigne_fixe'] = (
            fixe_b2b_data.get('prime_enseigne', {}).get(code, {}).get('montant_calcule', 0) +
            fixe_b2c_data.get('prime_enseigne', {}).get(code, {}).get('montant_calcule', 0)
        )
        
        # Prime objectif mobile = Mobile + DarBox
        primes['prime_objectif_mobile'] = (
            mobile_data.get('prime_objectif', {}).get(code, {}).get('montant_calcule', 0) +
            darbox_data.get('prime_objectif', {}).get(code, {}).get('montant_calcule', 0)
        )
        
        # Comm fixe global = Activations Fixe B2B + B2C
        primes['comm_fixe_global'] = (
            fixe_b2b_data.get('activations', {}).get(code, {}).get('montant_calcule', 0) +
            fixe_b2c_data.get('activations', {}).get(code, {}).get('montant_calcule', 0)
        )
        
        # Prime d'accès fixe (PA fixe global) = B2B + B2C
        primes['pa_fixe_global'] = (
            fixe_b2b_data.get('prime_acces', {}).get(code, {}).get('montant_calcule', 0) +
            fixe_b2c_data.get('prime_acces', {}).get(code, {}).get('montant_calcule', 0)
        )
        
        # Prime objectif fixe = Fixe B2B + B2C
        primes['prime_objectif_fixe'] = (
            fixe_b2b_data.get('prime_objectif', {}).get(code, {}).get('montant_calcule', 0) +
            fixe_b2c_data.get('prime_objectif', {}).get(code, {}).get('montant_calcule', 0)
        )
        
        # Pénalité = Mobile + Darbox + Fixe B2C (négatif) - PAS B2B
        coef_penalite = self.coefficients['penalite']
        penalite_total = (
            mobile_data.get('penalite', {}).get(code, {}).get('montant_brut', 0) +
            darbox_data.get('penalite', {}).get(code, {}).get('montant_brut', 0) +
            fixe_b2c_data.get('penalite', {}).get(code, {}).get('montant_brut', 0)
        )
        primes['penalite'] = -abs(penalite_total * coef_penalite)  # Négatif avec coefficient
        
        # Stocker activations pour PDF détails
        mobile_act_data = mobile_data.get('activations', {}).get(code, {})
        darbox_act_data = darbox_data.get('activations', {}).get(code, {})
        primes['_activations'] = (
            list(mobile_act_data.get('activations', [])) +
            list(darbox_act_data.get('activations', []))
        )
        
        return primes

    def extraire_tous_codes(self, mobile_data, darbox_data, fixe_b2b_data, fixe_b2c_data):
        """Extrait tous les codes uniques présents dans les 4 fichiers liquidation"""
        codes = set()
        for data in [mobile_data, darbox_data, fixe_b2b_data, fixe_b2c_data]:
            if not data:
                continue
            for val in data.values():
                if isinstance(val, dict):
                    codes.update(str(k) for k in val.keys())
        return codes
