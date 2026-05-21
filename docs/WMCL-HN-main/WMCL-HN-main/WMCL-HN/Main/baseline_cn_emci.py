import scipy.io as scio
import numpy as np
import pandas as pd
from sklearn.model_selection import cross_val_score, KFold
from sklearn.svm import SVC
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score, recall_score, roc_auc_score, f1_score, make_scorer

# ===================== 1. 加载你的 CN vs EMCI 数据 =====================
print("🔹 正在加载 adni_cn_emci.mat ...")

data = scio.loadmat("adni_cn_emci.mat")

# 加载 CN 和 EMCI 数据
cn_mri = data["mycn"][0,0]
cn_pet = data["mycn"][1,0]
cn_csf = data["mycn"][2,0]
cn_gnd = data["mycn"][3,0].ravel()

emci_mri = data["myemci"][0,0]
emci_pet = data["myemci"][1,0]
emci_csf = data["myemci"][2,0]
emci_gnd = data["myemci"][3,0].ravel()

# 合并所有数据
X_mri = np.vstack([cn_mri, emci_mri])
X_pet = np.vstack([cn_pet, emci_pet])
X_csf = np.vstack([cn_csf, emci_csf])
X = np.hstack([X_mri, X_pet, X_csf])  # 多模态拼接
y = np.hstack([cn_gnd, emci_gnd])

print(f"✅ 数据加载完成！总样本数：{len(y)}")
print(f"   CN：{len(cn_gnd)} 个")
print(f"   EMCI：{len(emci_gnd)} 个")
print(f"   特征维度：{X.shape[1]}")

# 标准化
scaler = StandardScaler()
X = scaler.fit_transform(X)

# ===================== 2. 5折交叉验证 =====================
kf = KFold(n_splits=5, shuffle=True, random_state=42)

# 评价指标
scoring = {
    'acc': 'accuracy',
    'recall': make_scorer(recall_score),
    'f1': make_scorer(f1_score),
    'auc': make_scorer(roc_auc_score, needs_proba=True)
}

# ===================== 3. 定义模型 =====================
models = {
    "LR": LogisticRegression(max_iter=1000),
    "SVM": SVC(kernel='linear', probability=True),
    "XGBoost": GradientBoostingClassifier()
}

# ===================== 4. 开始训练 =====================
results = []

print("\n" + "="*60)
print("📌 开始运行传统基线模型（LR / SVM / XGBoost）")
print("="*60)

for name, clf in models.items():
    acc_scores = []
    sen_scores = []
    spec_scores = []
    f1_scores = []
    auc_scores = []

    for train_idx, test_idx in kf.split(X):
        X_train, X_test = X[train_idx], X[test_idx]
        y_train, y_test = y[train_idx], y[test_idx]

        clf.fit(X_train, y_train)
        y_pred = clf.predict(X_test)
        y_prob = clf.predict_proba(X_test)[:,1]

        acc = accuracy_score(y_test, y_pred)
        sen = recall_score(y_test, y_pred, pos_label=1)
        spec = recall_score(y_test, y_pred, pos_label=0)
        f1 = f1_score(y_test, y_pred)
        auc = roc_auc_score(y_test, y_prob)

        acc_scores.append(acc)
        sen_scores.append(sen)
        spec_scores.append(spec)
        f1_scores.append(f1)
        auc_scores.append(auc)

    # 计算平均值
    acc_mean = np.mean(acc_scores)
    sen_mean = np.mean(sen_scores)
    spec_mean = np.mean(spec_scores)
    f1_mean = np.mean(f1_scores)
    auc_mean = np.mean(auc_scores)

    results.append([name, acc_mean, sen_mean, spec_mean, f1_mean, auc_mean])

    print(f"\n【{name}】")
    print(f"ACC：{acc_mean:.2%}")
    print(f"SEN：{sen_mean:.2%}")
    print(f"SPEC：{spec_mean:.2%}")
    print(f"F1：{f1_mean:.2%}")
    print(f"AUC：{auc_mean:.2%}")

# ===================== 5. 保存成 Excel =====================
df = pd.DataFrame(results, columns=["Model", "ACC", "SEN", "SPEC", "F1", "AUC"])
df.to_excel("baseline_cn_emci_result.xlsx", index=False)

print("\n" + "="*60)
print("🎉 全部完成！")
print("✅ 基线结果已保存到 baseline_cn_emci_result.xlsx")
print("可以直接写进论文对比表！")