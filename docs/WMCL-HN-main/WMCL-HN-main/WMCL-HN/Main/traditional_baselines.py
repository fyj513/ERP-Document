import numpy as np
import warnings
import sys
import os

# 屏蔽无关警告
warnings.filterwarnings("ignore")
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 导入原代码的工具
from Other.load_data import data_load
from Other.metrics import compute_metrics

# 全局配置（和SVM实验完全一致，保证公平）
RANDOM_SEED = 42
N_SPLITS = 5
DATA_PATH = 'adni_data.mat'

# -------------------------- 1. 加载AD vs NC数据（和之前完全一致） --------------------------
def load_ad_nc_data():
    print("正在加载NC（健康人）数据...")
    mri_nc, pet_nc, csf_nc, gnd_nc = data_load(DATA_PATH, 'mync')
    print("正在加载AD（患者）数据...")
    mri_ad, pet_ad, csf_ad, gnd_ad = data_load(DATA_PATH, 'myad')

    # 合并数据
    mri_all = np.concatenate([mri_nc, mri_ad], axis=0)
    pet_all = np.concatenate([pet_nc, pet_ad], axis=0)
    csf_all = np.concatenate([csf_nc, csf_ad], axis=0)
    labels_all = np.concatenate([gnd_nc, gnd_ad], axis=0)
    all_features = np.concatenate([mri_all, pet_all, csf_all], axis=1)

    print("\n✅ 数据加载完成！")
    print(f"总样本数：{len(labels_all)} | 特征维度：{all_features.shape[1]}")
    print(f"标签分布：0(NC)={np.sum(labels_all==0)}个，1(AD)={np.sum(labels_all==1)}个")

    return all_features, labels_all

# -------------------------- 2. 定义所有要跑的基线模型 --------------------------
def get_baseline_model(name):
    """根据基线名，返回模型和对应的超参数搜索空间"""
    if name == "LogisticRegression":
        model = LogisticRegression(class_weight='balanced', random_state=RANDOM_SEED, max_iter=10000)
        param_grid = {'C': [0.001, 0.01, 0.1, 1, 10, 100]}
    elif name == "RandomForest":
        model = RandomForestClassifier(class_weight='balanced', random_state=RANDOM_SEED, n_jobs=1)
        param_grid = {'n_estimators': [50, 100, 200], 'max_depth': [3, 5, 10, None]}
    elif name == "XGBoost":
        model = XGBClassifier(scale_pos_weight=131/84, random_state=RANDOM_SEED, n_jobs=1, use_label_encoder=False, eval_metric='logloss')
        param_grid = {'n_estimators': [50, 100, 200], 'max_depth': [2, 3, 5], 'learning_rate': [0.01, 0.1, 0.3]}
    elif name == "KNN":
        model = KNeighborsClassifier(n_jobs=1)
        param_grid = {'n_neighbors': [3,5,7,9,11]}
    else:
        raise ValueError("基线名错误！")
    return model, param_grid

# -------------------------- 3. 单基线五折实验函数 --------------------------
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import StratifiedKFold, GridSearchCV
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from xgboost import XGBClassifier
from sklearn.neighbors import KNeighborsClassifier

def run_single_baseline(X, y, baseline_name):
    skf = StratifiedKFold(n_splits=N_SPLITS, shuffle=True, random_state=RANDOM_SEED)
    fold_results = []

    print(f"\n{'='*50}")
    print(f"开始运行基线：{baseline_name}")
    print(f"{'='*50}")

    for fold_idx, (train_idx, test_idx) in enumerate(skf.split(X, y)):
        print(f"\n--- 第 {fold_idx+1} 折 ---")
        X_train, X_test = X[train_idx], X[test_idx]
        y_train, y_test = y[train_idx], y[test_idx]

        # 标准化（除了树模型，其他都需要）
        if baseline_name not in ["RandomForest", "XGBoost"]:
            scaler = StandardScaler()
            X_train_scaled = scaler.fit_transform(X_train)
            X_test_scaled = scaler.transform(X_test)
        else:
            # 树模型不需要标准化
            X_train_scaled = X_train
            X_test_scaled = X_test

        # 获取模型和超参数
        model, param_grid = get_baseline_model(baseline_name)

        # 网格搜索调参
        grid_search = GridSearchCV(model, param_grid, cv=5, scoring='accuracy', n_jobs=1)
        grid_search.fit(X_train_scaled, y_train)
        best_model = grid_search.best_estimator_
        print(f"最优参数：{grid_search.best_params_}")

        # 预测
        y_pred = best_model.predict(X_test_scaled)
        y_prob = best_model.predict_proba(X_test_scaled)

        # 计算指标（和你的原模型完全一致）
        acc, sen, spe, f1, auc = compute_metrics(y_test, y_prob)
        metrics = {"ACC": acc, "SEN": sen, "SPE": spe, "F1": f1, "AUC": auc}
        fold_results.append(metrics)
        print(f"当前折指标：{metrics}")

    # 计算平均结果
    print(f"\n===== {baseline_name} 五折平均结果 =====")
    avg_metrics = {}
    for key in fold_results[0].keys():
        avg_metrics[key] = np.mean([m[key] for m in fold_results])
        print(f"{key}: {avg_metrics[key]:.4f}")

    return {"每折结果": fold_results, "平均结果": avg_metrics}

# -------------------------- 4. 主函数：跑所有基线 --------------------------
if __name__ == "__main__":
    # 加载数据
    X_all, y_all = load_ad_nc_data()

    # 要跑的基线列表
    baselines = ["LogisticRegression", "RandomForest", "XGBoost", "KNN"]

    # 循环跑所有基线
    all_results = {}
    for baseline in baselines:
        res = run_single_baseline(X_all, y_all, baseline)
        all_results[baseline] = res

    # 保存结果
    np.save("traditional_baselines_results.npy", all_results, allow_pickle=True)
    print(f"\n{'='*60}")
    print("✅ 所有传统基线实验完成！结果已保存到 traditional_baselines_results.npy")
    print(f"{'='*60}")

    # 打印最终汇总结果
    print("\n📊 所有基线最终汇总结果（AD vs NC 五折平均）：")
    print("-"*100)
    for baseline in baselines:
        avg = all_results[baseline]["平均结果"]
        print(f"{baseline}: ACC={avg['ACC']:.2f}%, SEN={avg['SEN']:.2f}%, SPE={avg['SPE']:.2f}%, F1={avg['F1']:.2f}%, AUC={avg['AUC']:.2f}%")
    print("-"*100)