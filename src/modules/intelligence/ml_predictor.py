"""
ml_predictor.py - O Cérebro Quântico (Machine Learning)
Valida sinais técnicos usando probabilidade estatística (Random Forest).
"""

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
import joblib
import os
import logging

# Configuração
logger = logging.getLogger(__name__)

class MLPredictor:
    def __init__(self):
        self.model = None
        self.is_trained = False
        self.feature_cols = ['rsi', 'adx', 'atr_pct', 'vol_ratio', 'dist_from_bb_lower']
        
    def prepare_features(self, df):
        """Transforma candles brutos em features para o modelo."""
        try:
            # Garante que temos os indicadores técnicos (já calculados pelo pandas-ta no scalper ou aqui)
            # Assumindo que o DF já vem com RSI, ADX, ATR, etc. do scalper_blindado,
            # mas por segurança recalculamos o básico se faltar.
            
            # Copia para não alterar o original
            data = df.copy()
            
            # Limpeza
            data = data.dropna()
            
            # Feature Engineering Básica
            if 'rsi' not in data.columns:
                return None
                
            # Verifica colunas necessárias
            missing = [c for c in self.feature_cols if c not in data.columns and c != 'dist_from_bb_lower']
            if missing:
                # Se faltar dados, tenta calcular ou retorna erro
                return None

            return data[self.feature_cols]
        except Exception as e:
            logger.error(f"Erro ao preparar features ML: {e}")
            return None

    def train_model(self, full_history_df):
        """
        Treina o modelo com base no histórico.
        Alvo (Target): Preço subiu > 1.0% nos próximos 3 candles (3 horas)?
        """
        try:
            if full_history_df is None or len(full_history_df) < 200:
                logger.warning("ML: Dados insuficientes para treino (<200 candles).")
                return False

            df = full_history_df.copy()
            
            # --- Criação do Target (O que queremos prever?) ---
            # Olhamos 3 velas para frente (3 horas)
            # Se o fechamento futuro > fechamento atual + 1.0% (lucro), Target = 1
            # Taxa de sucesso mínima para considerar "Win"
            
            df['future_close'] = df['close'].shift(-3)
            df['target'] = (df['future_close'] > df['close'] * 1.01).astype(int)
            
            # --- Feature Engineering ---
            # Precisamos calcular as mesmas métricas que o scalper usa
            # Como o DF pode vir "cru", vamos garantir
            # (Simplificação: assumimos que o chamador já passa um DF rico ou aceitamos treinar com o que tem)
            
            # Calculando 'dist_from_bb_lower' se tiver bandas
            if 'bb_lower' in df.columns and 'close' in df.columns:
                df['dist_from_bb_lower'] = (df['close'] - df['bb_lower']) / df['close']
            else:
                df['dist_from_bb_lower'] = 0.0

            # Remove linhas com NaN (gerados pelo shift ou indicadores)
            df = df.dropna()
            
            if len(df) < 100:
                return False

            X = df[self.feature_cols]
            y = df['target']
            
            # Treinamento
            # RandomForest é robusto e não precisa de muita normalização
            self.model = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42)
            self.model.fit(X, y)
            
            self.is_trained = True
            
            # Avaliação rápida (opcional)
            score = self.model.score(X, y)
            logger.info(f"🧠 ML: Modelo treinado! Acurácia no treino: {score:.2f}")
            print(f"🧠 Cérebro ML treinado com {len(df)} candles. Acurácia Base: {score*100:.1f}%")
            
            # Salva dados de treino para auditoria
            try:
                os.makedirs('data', exist_ok=True)
                # Salva colunas de features + target + close (para referência) + time
                export_cols = ['time', 'close', 'target'] + self.feature_cols
                # Garante que as colunas existem antes de salvar
                valid_cols = [c for c in export_cols if c in df.columns]
                df[valid_cols].to_csv('data/ml_training_data.csv', index=False)
                logger.info("💾 Dados de treino ML salvos em data/ml_training_data.csv")
            except Exception as save_err:
                logger.error(f"Erro ao salvar CSV de treino: {save_err}")
            
            return True
            
        except Exception as e:
            logger.error(f"Erro no treino ML: {e}")
            return False

    def predict_score(self, current_indicators):
        """
        Retorna a probabilidade de sucesso (%) para o candle atual.
        current_indicators: dict com 'rsi', 'adx', etc.
        """
        if not self.is_trained or self.model is None:
            return 50.0 # Sem opinião (Neturo)
            
        try:
            # Monta o vetor de input na mesma ordem das colunas de treino
            input_data = pd.DataFrame([current_indicators])
            
            # Garante colunas faltantes com 0.0
            for col in self.feature_cols:
                if col not in input_data.columns:
                    input_data[col] = 0.0
            
            # Reordena
            X_new = input_data[self.feature_cols]
            
            # Pega a probabilidade da classe 1 (SUCESSO)
            probs = self.model.predict_proba(X_new)
            success_prob = probs[0][1] * 100.0 # 0 a 100
            
            return float(success_prob)
            
        except Exception as e:
            logger.error(f"Erro na previsão ML: {e}")
            return 50.0

# Instância Global (Singleton)
predictor = MLPredictor()
