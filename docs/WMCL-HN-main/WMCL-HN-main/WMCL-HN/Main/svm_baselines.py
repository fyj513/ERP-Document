import numpy as np
import scipy.io as sio
import warnings
import sys
import os

# 屏蔽无关警告
warnings.filterwarnings("ignore")
# 让Python能找到Other文件夹里的metrics.py（适配你的目录结构）
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# -------------------------- 【必须修改！】导入你的评估函数 --------------------------
# 把这里的函数名，改成你Other/metrics.py里的真实函数名！
from Other.metrics import calculate_metrics

# -------------------------- 全局配置（和原论文100%对齐，不用改） --------------------------
RANDOM_SEED = 42  # 固定随机种子，和原模型一致，保证结果可复现
N_SPLITS = 5       # 五折分层交叉验证，和论文完全一致
DATA_PATH = 'adni_data.mat'  # 你的数据路径，不用改

# -------------------------- 1. 数据加载和任务准备 --------------------------
def load_data():
    """加载adni_data.mat，和原论文用完全一样的数据"""
    data = sio.loadmat(DATA_PATH)
    
    # -------------------------- 【必须修改！】对应你的数据key名 --------------------------
    mri = data['mri']      # MRI特征，正常形状是 (452, 90)
    pet = data['pet']      # PET特征，正常形状是 (452, 90)
    csf = data['csf']      # CSF特征，正常形状是 (452, 3)
    all_labels = data['label'].squeeze()  # 标签，形状 (452,)
    # -------------------------------------------------------------------------------------
    
    # 拼接全量特征（给基础SVM、Lasso-SVM用）
    all_features = np.concatenate([mri, pet, csf], axis=1)
    
    return {
        "mri": mri,
        "pet": pet,
        "csf": csf,
        "all_features": all_features,
        "labels": all_labels
    }

def get_task_data(full_data, task_name):
    """
    筛选对应任务的数据，和论文的4个任务完全对应
    可选任务："ADvsNC" / "LMCIvsNC" / "EMCIvsNC" / "4_class"
    """
    all_feat = full_data['all_features']
    mri = full_data['mri']
    pet = full_data['pet']
    csf = full_data['csf']
    labels = full_data['labels']

    if task_name == "ADvsNC":
        # 筛选AD(3)和健康人(0)
        mask = np.isin(labels, [0, 3])
        y = labels[mask]
        y = np.where(y == 3, 1, 0)  # 二分类标签：1=AD，0=NC
    elif task_name == "LMCIvsNC":
        # 筛选晚期轻度认知障碍(2)和健康人(0)
        mask = np.isin(labels, [0, 2])
        y = labels[mask]
        y = np.where(y == 2, 1, 0)  # 二分类标签：1=LMCI，0=NC
    elif task_name == "EMCIvsNC":
        # 筛选早期轻度认知障碍(1)和健康人(0)
        mask = np.isin(labels, [0, 1])
        y = labels[mask]
        y = np.where(y == 1, 1, 0)  # 二分类标签：1=EMCI，0=NC
    elif task_name == "4_class":
        # 四分类任务，直接用原始标签
        mask = np.ones_like(labels, dtype=bool)
        y = labels
    else:
        raise ValueError("任务名错误！只能选：ADvsNC / LMCIvsNC / EMCIvsNC / 4_class")
    
    # 返回对应的数据
    return {
        "X_all": all_feat[mask],  # 拼接后的全量特征
        "X_mri": mri[mask],       # 单独的MRI特征
        "X_pet": pet[mask],       # 单独的PET特征
        "X_csf": csf[mask],       # 单独的CSF特征
        "y": y                     # 对应任务的标签
    }

# -------------------------- 2. 4个SVM基线的核心实现 --------------------------
# 导入SVM和相关工具
from sklearn.svm import SVC
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import StratifiedKFold, GridSearchCV
from sklearn.linear_model import Lasso
from sklearn.feature_selection import SelectFromModel
from sklearn.metrics.pairwise import linear_kernel

def run_single_baseline(task_data, baseline_name):
    """
    跑单个SVM基线的五折实验
    baseline_name可选："BaseSVM" / "LassoSVM" / "MKSVM" / "LassoMKSVM"
    """
    # 取出当前任务的数据
    X_all = task_data["X_all"]
    X_mri = task_data["X_mri"]
    X_pet = task_data["X_pet"]
    X_csf = task_data["X_csf"]
    y = task_data["y"]

    # 五折分层交叉验证（和论文完全一致）
    skf = StratifiedKFold(n_splits=N_SPLITS, shuffle=True, random_state=RANDOM_SEED)
    fold_results = []  # 保存每一折的指标

    print(f"\n===== 开始运行基线：{baseline_name} =====")

    for fold_idx, (train_idx, test_idx) in enumerate(skf.split(X_all, y)):
        print(f"\n--- 第 {fold_idx+1} 折 ---")

        # 1. 划分训练集和测试集（所有方法共用这个划分，保证公平）
        # 全量特征的划分
        X_train_all, X_test_all = X_all[train_idx], X_all[test_idx]
        # 单模态特征的划分
        mri_train, mri_test = X_mri[train_idx], X_mri[test_idx]
        pet_train, pet_test = X_pet[train_idx], X_pet[test_idx]
        csf_train, csf_test = X_csf[train_idx], X_csf[test_idx]
        # 标签划分
        y_train, y_test = y[train_idx], y[test_idx]

        # 2. 不同基线的处理逻辑
        if baseline_name == "BaseSVM":
            # ========== 1. 基础SVM：全量特征拼接+标准化+线性SVM ==========
            # 标准化：只在训练集拟合，绝对不能用测试集，防止数据泄露！
            scaler = StandardScaler()
            X_train_scaled = scaler.fit_transform(X_train_all)
            X_test_scaled = scaler.transform(X_test_all)

            # 网格搜索调优超参数（和论文基线对齐）
            param_grid = {
                'C': [0.001, 0.01, 0.1, 1, 10, 100],  # 正则化系数
                'kernel': ['linear']  # 高维医学特征用线性核效果最好，和论文一致
            }
            grid_search = GridSearchCV(
                SVC(probability=True, random_state=RANDOM_SEED, class_weight='balanced'),
                param_grid, cv=5, scoring='accuracy', n_jobs=-1
            )
            grid_search.fit(X_train_scaled, y_train)
            best_model = grid_search.best_estimator_
            print(f"最优参数：{grid_search.best_params_}")

            # 预测
            y_pred = best_model.predict(X_test_scaled)
            y_prob = best_model.predict_proba(X_test_scaled)

        elif baseline_name == "LassoSVM":
            # ========== 2. Lasso-SVM：Lasso特征筛选+SVM ==========
            # 先标准化
            scaler = StandardScaler()
            X_train_scaled = scaler.fit_transform(X_train_all)
            X_test_scaled = scaler.transform(X_test_all)

            # Lasso特征筛选：只在训练集拟合，防止数据泄露
            lasso = Lasso(alpha=0.01, max_iter=10000, random_state=RANDOM_SEED)
            selector = SelectFromModel(lasso)
            X_train_selected = selector.fit_transform(X_train_scaled, y_train)
            X_test_selected = selector.transform(X_test_scaled)
            print(f"特征筛选：{X_train_scaled.shape[1]}维 → {X_train_selected.shape[1]}维")

            # 如果筛选后特征数为0，用原始特征兜底
            if X_train_selected.shape[1] == 0:
                print("警告：Lasso筛选后无特征，改用原始特征")
                X_train_selected, X_test_selected = X_train_scaled, X_test_scaled

            # 网格搜索调参
            param_grid = {'C': [0.001, 0.01, 0.1, 1, 10, 100], 'kernel': ['linear']}
            grid_search = GridSearchCV(
                SVC(probability=True, random_state=RANDOM_SEED, class_weight='balanced'),
                param_grid, cv=5, scoring='accuracy', n_jobs=-1
            )
            grid_search.fit(X_train_selected, y_train)
            best_model = grid_search.best_estimator_
            print(f"最优参数：{grid_search.best_params_}")

            # 预测
            y_pred = best_model.predict(X_test_selected)
            y_prob = best_model.predict_proba(X_test_selected)

        elif baseline_name == "MKSVM":
            # ========== 3. MKSVM：多模态多核融合SVM ==========
            # 每个模态单独标准化（更合理，适配不同模态的分布）
            scaler_mri = StandardScaler()
            scaler_pet = StandardScaler()
            scaler_csf = StandardScaler()

            mri_train_scaled = scaler_mri.fit_transform(mri_train)
            pet_train_scaled = scaler_pet.fit_transform(pet_train)
            csf_train_scaled = scaler_csf.fit_transform(csf_train)

            mri_test_scaled = scaler_mri.transform(mri_test)
            pet_test_scaled = scaler_pet.transform(pet_test)
            csf_test_scaled = scaler_csf.transform(csf_test)

            # 计算每个模态的线性核矩阵
            # 训练集核矩阵
            K_mri_train = linear_kernel(mri_train_scaled, mri_train_scaled)
            K_pet_train = linear_kernel(pet_train_scaled, pet_train_scaled)
            K_csf_train = linear_kernel(csf_train_scaled, csf_train_scaled)
            # 等权重融合核矩阵（和论文基线对齐）
            K_train = (K_mri_train + K_pet_train + K_csf_train) / 3

            # 测试集核矩阵（必须和训练集计算，不能自己和自己算！）
            K_mri_test = linear_kernel(mri_test_scaled, mri_train_scaled)
            K_pet_test = linear_kernel(pet_test_scaled, pet_train_scaled)
            K_csf_test = linear_kernel(csf_test_scaled, csf_train_scaled)
            K_test = (K_mri_test + K_pet_test + K_csf_test) / 3

            # 网格搜索调参（注意kernel='precomputed'，用我们提前算好的核矩阵）
            param_grid = {'C': [0.001, 0.01, 0.1, 1, 10, 100]}
            grid_search = GridSearchCV(
                SVC(kernel='precomputed', probability=True, random_state=RANDOM_SEED, class_weight='balanced'),
                param_grid, cv=5, scoring='accuracy', n_jobs=-1
            )
            grid_search.fit(K_train, y_train)
            best_model = grid_search.best_estimator_
            print(f"最优参数：{grid_search.best_params_}")

            # 预测
            y_pred = best_model.predict(K_test)
            y_prob = best_model.predict_proba(K_test)

        elif baseline_name == "LassoMKSVM":
            # ========== 4. Lasso-MKSVM：单模态Lasso筛选+多核融合 ==========
            # 每个模态单独标准化
            scaler_mri = StandardScaler()
            scaler_pet = StandardScaler()
            scaler_csf = StandardScaler()

            mri_train_scaled = scaler_mri.fit_transform(mri_train)
            pet_train_scaled = scaler_pet.fit_transform(pet_train)
            csf_train_scaled = scaler_csf.fit_transform(csf_train)

            mri_test_scaled = scaler_mri.transform(mri_test)
            pet_test_scaled = scaler_pet.transform(pet_test)
            csf_test_scaled = scaler_csf.transform(csf_test)

            # 给每个模态单独做Lasso特征筛选
            def lasso_select(train_feat, test_feat, y_tr):
                lasso = Lasso(alpha=0.01, max_iter=10000, random_state=RANDOM_SEED)
                selector = SelectFromModel(lasso)
                train_sel = selector.fit_transform(train_feat, y_tr)
                test_sel = selector.transform(test_feat)
                # 兜底：如果筛选后没特征，用原始特征
                if train_sel.shape[1] == 0:
                    return train_feat, test_feat
                return train_sel, test_sel

            # 对三个模态分别筛选
            mri_train_sel, mri_test_sel = lasso_select(mri_train_scaled, mri_test_scaled, y_train)
            pet_train_sel, pet_test_sel = lasso_select(pet_train_scaled, pet_test_scaled, y_train)
            csf_train_sel, csf_test_sel = lasso_select(csf_train_scaled, csf_test_scaled, y_train)
            print(f"MRI筛选后：{mri_train_scaled.shape[1]}维 → {mri_train_sel.shape[1]}维")
            print(f"PET筛选后：{pet_train_scaled.shape[1]}维 → {pet_train_sel.shape[1]}维")
            print(f"CSF筛选后：{csf_train_scaled.shape[1]}维 → {csf_train_sel.shape[1]}维")

            # 计算筛选后的核矩阵
            K_mri_train = linear_kernel(mri_train_sel, mri_train_sel)
            K_pet_train = linear_kernel(pet_train_sel, pet_train_sel)
            K_csf_train = linear_kernel(csf_train_sel, csf_train_sel)
            K_train = (K_mri_train + K_pet_train + K_csf_train) / 3

            K_mri_test = linear_kernel(mri_test_sel, mri_train_sel)
            K_pet_test = linear_kernel(pet_test_sel, pet_train_sel)
            K_csf_test = linear_kernel(csf_test_sel, csf_train_sel)
            K_test = (K_mri_test + K_pet_test + K_csf_test) / 3

            # 网格搜索调参
            param_grid = {'C': [0.001, 0.01, 0.1, 1, 10, 100]}
            grid_search = GridSearchCV(
                SVC(kernel='precomputed', probability=True, random_state=RANDOM_SEED, class_weight='balanced'),
                param_grid, cv=5, scoring='accuracy', n_jobs=-1
            )
            grid_search.fit(K_train, y_train)
            best_model = grid_search.best_estimator_
            print(f"最优参数：{grid_search.best_params_}")

            # 预测
            y_pred = best_model.predict(K_test)
            y_prob = best_model.predict_proba(K_test)

        else:
            raise ValueError("基线名错误！只能选：BaseSVM / LassoSVM / MKSVM / LassoMKSVM")

        # 3. 计算评估指标（用你原模型的metrics函数，保证评估标准100%一致）
        # -------------------------- 【必须修改！】适配你的metrics函数 --------------------------
        # 如果你的函数输入不一样，这里要对应修改！
        metrics = calculate_metrics(y_test, y_pred, y_prob)
        # -------------------------------------------------------------------------------------
        fold_results.append(metrics)
        print(f"当前折指标：{metrics}")

    # 4. 计算五折的平均结果
    print(f"\n===== {baseline_name} 五折平均结果 =====")
    avg_metrics = {}
    for key in fold_results[0].keys():
        avg_metrics[key] = np.mean([m[key] for m in fold_results])
        print(f"{key}: {avg_metrics[key]:.4f}")

    return {
        "每折结果": fold_results,
        "平均结果": avg_metrics
    }

# -------------------------- 3. 主函数：跑所有任务和所有基线 --------------------------
if __name__ == "__main__":
    # 1. 加载数据
    full_data = load_data()
    print("数据加载完成！")

    # 2. 定义要跑的任务和基线
    # 论文里的4个任务，你可以先跑一个试试，比如先跑["ADvsNC"]
    tasks = ["ADvsNC", "LMCIvsNC", "EMCIvsNC", "4_class"]
    # 4个SVM基线
    baselines = ["BaseSVM", "LassoSVM", "MKSVM", "LassoMKSVM"]

    # 保存所有结果
    all_results = {}

    # 3. 循环跑所有任务和基线
    for task in tasks:
        print(f"\n{'#'*60}")
        print(f"开始处理任务：{task}")
        print(f"{'#'*60}")

        # 获取当前任务的数据
        task_data = get_task_data(full_data, task)
        all_results[task] = {}

        # 跑每个基线
        for baseline in baselines:
            res = run_single_baseline(task_data, baseline)
            all_results[task][baseline] = res

    # 4. 保存所有结果，方便后续整理表格
    np.save("svm_all_baselines_results.npy", all_results, allow_pickle=True)
    print("\n✅ 所有实验完成！结果已保存到 svm_all_baselines_results.npy")

    # 5. 打印最终的汇总结果，方便你直接复制
    print(f"\n{'='*80}")
    print("最终汇总结果（五折平均ACC）：")
    print(f"{'='*80}")
    for task in tasks:
        print(f"\n【任务：{task}】")
        for baseline in baselines:
            acc = all_results[task][baseline]["平均结果"]["ACC"]
            print(f"  {baseline}: {acc:.4f}")