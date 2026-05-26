"""薪资预测 — XGBoost 模型 + 特征工程。

模型需离线训练后序列化为 salary_model.json 文件。
在线预测时加载模型并作推理。
"""

import math
import os
from typing import Any

import numpy as np


class SalaryPredictor:
    """XGBoost 薪资预测器。"""

    CATEGORY_MAPPINGS: dict[str, dict[str, int]] = {
        "education_level": {"high_school": 0, "associate": 1, "bachelor": 2, "master": 3, "phd": 4},
        "company_size": {"startup": 0, "small": 1, "medium": 2, "large": 3, "enterprise": 4},
    }

    # 职位基础薪资映射（CNY）
    ROLE_BASELINES: dict[str, dict[str, float]] = {
        "software engineer": {"Beijing": 250000, "Shanghai": 240000, "Shenzhen": 230000, "Hangzhou": 220000, "default": 200000},
        "senior software engineer": {"Beijing": 450000, "Shanghai": 430000, "Shenzhen": 410000, "Hangzhou": 390000, "default": 350000},
        "data scientist": {"Beijing": 350000, "Shanghai": 340000, "Shenzhen": 330000, "Hangzhou": 310000, "default": 280000},
        "machine learning engineer": {"Beijing": 420000, "Shanghai": 400000, "Shenzhen": 390000, "Hangzhou": 370000, "default": 340000},
        "product manager": {"Beijing": 320000, "Shanghai": 310000, "Shenzhen": 300000, "Hangzhou": 280000, "default": 250000},
        "devops engineer": {"Beijing": 300000, "Shanghai": 290000, "Shenzhen": 280000, "Hangzhou": 260000, "default": 240000},
        "frontend developer": {"Beijing": 280000, "Shanghai": 270000, "Shenzhen": 260000, "Hangzhou": 240000, "default": 220000},
        "backend developer": {"Beijing": 300000, "Shanghai": 290000, "Shenzhen": 280000, "Hangzhou": 260000, "default": 240000},
        "full-stack developer": {"Beijing": 310000, "Shanghai": 300000, "Shenzhen": 280000, "Hangzhou": 260000, "default": 250000},
        "java developer": {"Beijing": 280000, "Shanghai": 270000, "Shenzhen": 260000, "Hangzhou": 240000, "default": 220000},
        "python developer": {"Beijing": 260000, "Shanghai": 250000, "Shenzhen": 240000, "Hangzhou": 220000, "default": 200000},
    }

    def __init__(self, model_path: str | None = None):
        self._model = None
        self._model_path = model_path or os.path.join(
            os.path.dirname(__file__), "salary_model.json"
        )

    async def predict(self, params: dict[str, Any]) -> dict[str, Any]:
        """预测薪资范围。"""
        title = params.get("title", "").lower()
        location = params.get("location", "Beijing")
        experience_years = float(params.get("experience_years", 3))
        education = params.get("education_level", "bachelor")
        skills = params.get("skills", [])
        company_size = params.get("company_size", "medium")

        # 尝试 XGBoost 模型
        try:
            xgb_result = await self._xgboost_predict(params)
            if xgb_result:
                return xgb_result
        except Exception:
            pass

        # 规则降级预测
        return self._rule_based_predict(title, location, experience_years, education, skills, company_size)

    async def _xgboost_predict(self, params: dict[str, Any]) -> dict[str, Any] | None:
        """使用 XGBoost 模型预测。"""
        try:
            import xgboost as xgb
        except ImportError:
            return None

        if self._model is None:
            if not os.path.exists(self._model_path):
                return None
            self._model = xgb.Booster()
            self._model.load_model(self._model_path)

        features = self._extract_features(params)
        dmatrix = xgb.DMatrix(np.array([features]))
        pred = self._model.predict(dmatrix)

        median = float(pred[0])
        return {
            "predicted_min": round(median * 0.8, -3),
            "predicted_max": round(median * 1.2, -3),
            "predicted_median": round(median, -3),
            "currency": "CNY",
            "confidence": 0.75,
            "factors": self._compute_factors(params, median),
        }

    def _extract_features(self, params: dict[str, Any]) -> list[float]:
        """特征工程：将参数转为模型输入向量。"""
        title = params.get("title", "").lower()
        location = params.get("location", "Beijing")
        exp = float(params.get("experience_years", 3))
        education = params.get("education_level", "bachelor")
        skills = params.get("skills", [])
        company_size = params.get("company_size", "medium")

        features: list[float] = []

        # 职位特征（one-hot encoding）
        for role in list(self.ROLE_BASELINES.keys())[:10]:
            features.append(1.0 if role in title else 0.0)

        # 城市特征
        tier1 = ["Beijing", "Shanghai", "Shenzhen", "Hangzhou", "Guangzhou"]
        for city in tier1:
            features.append(1.0 if city.lower() in location.lower() else 0.0)

        # 工作经验
        features.append(exp)
        features.append(math.log1p(exp))
        features.append(exp ** 2)

        # 教育程度
        edu_map = {"high_school": 0, "associate": 1, "bachelor": 2, "master": 3, "phd": 4}
        features.append(float(edu_map.get(education, 2)))

        # 公司规模
        size_map = {"startup": 0, "small": 1, "medium": 2, "large": 3, "enterprise": 4}
        features.append(float(size_map.get(company_size, 2)))

        # 技能数量
        features.append(float(len(skills)))

        return features

    def _rule_based_predict(self, title: str, location: str, experience_years: float,
                            education: str, skills: list[str], company_size: str) -> dict[str, Any]:
        """基于规则的薪资预测（无模型时的降级方案）。"""
        # 找到最匹配的职位基线
        baseline = 200000.0
        for role, loc_map in self.ROLE_BASELINES.items():
            if role in title:
                baseline = loc_map.get(location, loc_map.get("default", 200000))
                break
        else:
            baseline = self.ROLE_BASELINES.get(
                "software engineer", {"default": 200000}
            ).get(location, 200000)

        # 经验调整
        exp_factor = 1.0 + (experience_years - 3) * 0.08
        exp_factor = max(0.6, min(exp_factor, 2.5))

        # 教育调整
        edu_factors = {"phd": 1.2, "master": 1.1, "bachelor": 1.0, "associate": 0.85, "high_school": 0.7}
        edu_factor = edu_factors.get(education, 1.0)

        # 技能调整
        premium_skills = {"machine learning", "deep learning", "kubernetes", "aws", "gcp", "azure",
                          "tensorflow", "pytorch", "spark", "kafka", "react", "go", "rust"}
        skill_bonus = sum(1.05 for s in skills if s.lower() in premium_skills)

        # 公司规模调整
        size_factors = {"enterprise": 1.15, "large": 1.05, "medium": 1.0, "small": 0.9, "startup": 0.8}
        size_factor = size_factors.get(company_size, 1.0)

        median = baseline * exp_factor * edu_factor * skill_bonus * size_factor

        return {
            "predicted_min": round(median * 0.8, -3),
            "predicted_max": round(median * 1.2, -3),
            "predicted_median": round(median, -3),
            "currency": "CNY",
            "confidence": 0.60,
            "factors": {
                "base_salary": baseline,
                "experience_multiplier": round(exp_factor, 2),
                "education_multiplier": round(edu_factor, 2),
                "skill_premium": round(skill_bonus, 2),
                "company_size_multiplier": round(size_factor, 2),
            },
        }

    def _compute_factors(self, params: dict[str, Any], median: float) -> dict[str, float]:
        return {
            "experience_years": float(params.get("experience_years", 3)),
            "skills_count": len(params.get("skills", [])),
            "education": self.CATEGORY_MAPPINGS["education_level"].get(
                params.get("education_level", "bachelor"), 2),
        }


# ── 离线训练辅助函数 ──────────────────────────────────────────────

def train_salary_model(salary_records: list[dict[str, Any]], output_path: str = "salary_model.json"):
    """离线训练 XGBoost 薪资预测模型。

    Args:
        salary_records: 训练数据列表，每条包含 title, location, experience_years,
                        education_level, company_size, skills, salary
        output_path: 模型保存路径
    """
    try:
        import xgboost as xgb
    except ImportError:
        raise ImportError("需要安装 xgboost")

    predictor = SalaryPredictor()
    X = np.array([predictor._extract_features(r) for r in salary_records])
    y = np.array([r["salary"] for r in salary_records])

    dtrain = xgb.DMatrix(X, label=y)

    params = {
        "max_depth": 6,
        "eta": 0.1,
        "objective": "reg:squarederror",
        "eval_metric": "rmse",
        "subsample": 0.8,
        "colsample_bytree": 0.8,
    }

    model = xgb.train(params, dtrain, num_boost_round=200)
    model.save_model(output_path)
    return model
