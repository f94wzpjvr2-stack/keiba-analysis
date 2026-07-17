from pathlib import Path
import pandas as pd
from keiba_ai.model import train_model, save_model

data_path=Path("data/live/training_rows.csv")
if not data_path.exists():
    raise SystemExit("学習データがありません")
df=pd.read_csv(data_path)
model,report=train_model(df)
save_model(model,"models/win_model.joblib")
print(report)
