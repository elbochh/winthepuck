from pathlib import Path

import nbformat as nbf


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "Project_Phase2_NHL.ipynb"

nb = nbf.v4.new_notebook()
nb["metadata"] = {
    "kernelspec": {
        "display_name": "Python 3",
        "language": "python",
        "name": "python3",
    },
    "language_info": {"name": "python", "version": "3"},
}

cells = []


def md(text: str) -> None:
    cells.append(nbf.v4.new_markdown_cell(text.strip()))


def code(text: str) -> None:
    cells.append(nbf.v4.new_code_cell(text.strip()))


md(
    """
# Project Phase 2 — Data Wrangling, Feature Selection and Train–Test Split

**Dataset:** NHL game-level winner-prediction data  
**Target:** `target_home_win` (1 = home-team win, 0 = away-team win)

This notebook completes the required exploratory data analysis (EDA), explains every code block, includes 10 visualizations with an inference after each, answers the four assigned questions, and creates a leakage-safe chronological train–test split.
"""
)

md(
    """
## Required EDA and data preparation

### Import the analysis libraries

The next code block imports the tools used to load and summarize the data (`pandas` and `numpy`) and to create the required charts (`matplotlib` and `seaborn`). The display and theme settings keep tables and figures readable and consistent.
"""
)
code(
    """
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from IPython.display import display

pd.set_option("display.max_columns", 30)
pd.set_option("display.float_format", lambda value: f"{value:,.3f}")
sns.set_theme(style="whitegrid", context="notebook")

DATA_PATH = Path("data/model_dataset.csv")
TARGET = "target_home_win"
"""
)

md(
    """
### Load and inspect the dataset

This block loads the CSV, converts the game date to a true date/time type, sorts games chronologically, and displays the dataset dimensions, date range, target values, and a five-row sample. Sorting now also makes the later time-based split reproducible.
"""
)
code(
    """
df = pd.read_csv(DATA_PATH, low_memory=False)
df["game_date"] = pd.to_datetime(df["game_date"], errors="coerce")
df = df.sort_values(["game_date", "game_id"]).reset_index(drop=True)

print(f"Rows: {df.shape[0]:,}")
print(f"Columns: {df.shape[1]:,}")
print(f"Date range: {df['game_date'].min().date()} to {df['game_date'].max().date()}")
print(f"Target values: {sorted(df[TARGET].dropna().unique().tolist())}")
display(df.head())
"""
)
md(
    """
**Inference:** The dataset contains 20,591 completed games, 143 attributes, and 16 NHL seasons from October 7, 2010 through June 14, 2026. The target is already encoded correctly as a binary variable.
"""
)

md(
    """
### Check data quality

The next block checks exact duplicate rows, duplicate game identifiers, invalid dates, invalid targets, and missingness. These tests identify anomalies before any feature analysis or data splitting is performed.
"""
)
code(
    """
quality_summary = pd.Series(
    {
        "exact_duplicate_rows": int(df.duplicated().sum()),
        "duplicate_game_ids": int(df["game_id"].duplicated().sum()),
        "missing_game_dates": int(df["game_date"].isna().sum()),
        "missing_targets": int(df[TARGET].isna().sum()),
        "invalid_target_values": int((~df[TARGET].isin([0, 1]) & df[TARGET].notna()).sum()),
        "total_missing_cells": int(df.isna().sum().sum()),
        "overall_missing_rate_pct": 100 * df.isna().mean().mean(),
    }
)
display(quality_summary.to_frame("value"))

all_missing_columns = df.columns[df.isna().all()].tolist()
print("Columns with 100% missing values:")
print(all_missing_columns)
"""
)
md(
    """
**Inference:** There are no duplicate rows, duplicate game IDs, invalid dates, missing targets, or invalid target values. Nine skater-summary attributes are entirely missing and cannot contribute information, so they are excluded from the modeling candidates. The remaining missing values mainly occur in early-season rolling statistics where a team has not yet played enough prior games.
"""
)

md(
    """
### Descriptive statistics

This code summarizes the target, final scores, and representative pre-game predictors. It reports count, average, variation, minimum, quartiles, and maximum so that scale, missingness, and possible extreme values can be compared.
"""
)
code(
    """
summary_columns = [
    TARGET,
    "home_score",
    "away_score",
    "rest_days_diff",
    "last_10_win_pct_diff",
    "season_points_pct_diff",
    "goal_diff_last_10_diff",
    "elo_diff",
    "elo_prob_home",
]
display(df[summary_columns].describe().T)
"""
)
md(
    """
**Inference:** Home teams won about 54.0% of games and averaged 3.046 goals, compared with 2.796 for away teams. The predictors use different scales—for example, percentages are near zero while Elo differences span hundreds of points—so scaling would be useful for scale-sensitive models. Large rest differences are plausible schedule extremes and should be investigated rather than automatically deleted.
"""
)

md(
    """
### Prepare valid pre-game feature candidates

This block creates a modeling table using only information available before a game starts. Post-game fields such as final scores and winner names are deliberately excluded because they would leak the answer. Completely empty columns are removed, while other missing values are retained for now so that imputation can later be fitted on the training set only.
"""
)
code(
    """
pregame_features = [
    "rest_days_diff",
    "games_last_3_days_diff",
    "games_last_7_days_diff",
    "games_last_14_days_diff",
    "back_to_back_diff",
    "last_5_win_pct_diff",
    "last_10_win_pct_diff",
    "last_5_goals_for_avg_diff",
    "last_5_goals_against_avg_diff",
    "last_10_shots_for_avg_diff",
    "last_10_shots_against_avg_diff",
    "season_points_pct_diff",
    "goal_diff_last_10_diff",
    "home_ice_split_win_pct_diff",
    "home_ice_split_goal_diff_avg_diff",
    "last_10_powerplay_goals_avg_diff",
    "last_10_penalty_minutes_avg_diff",
    "last_10_faceoff_win_pct_avg_diff",
    "last_10_blocked_shots_avg_diff",
    "last_10_hits_avg_diff",
    "last_10_giveaways_avg_diff",
    "last_10_takeaways_avg_diff",
    "last_10_es_shot_attempts_for_avg_diff",
    "last_10_es_shot_attempts_against_avg_diff",
    "last_10_es_shot_attempt_share_diff",
    "last_10_es_goals_for_avg_diff",
    "last_10_es_goals_against_avg_diff",
    "last_3_starting_goalie_save_pct_diff",
    "last_3_starting_goalie_goals_against_avg_diff",
    "last_3_starting_goalie_shots_against_avg_diff",
    "last_3_starting_goalie_quality_start_pct_diff",
    "h2h_games_last_365_days",
    "h2h_home_team_win_pct_last_5",
    "h2h_home_team_goal_diff_avg_last_5",
    "series_win_diff_before",
    "home_elimination_game",
    "away_elimination_game",
    "elo_diff",
    "decay_goal_diff_diff",
    "decay_win_rate_diff",
    "is_playoff",
]

pregame_features = [
    column for column in pregame_features
    if column in df.columns and not df[column].isna().all()
]
modeling_df = df.drop_duplicates(subset="game_id").dropna(subset=["game_date", TARGET]).copy()

print(f"Usable games: {len(modeling_df):,}")
print(f"Usable pre-game predictors: {len(pregame_features)}")
print("Excluded leakage examples: home_score, away_score, winner_team")
"""
)
md(
    """
**Inference:** All 20,591 games remain after validation and deduplication. The feature list contains 41 usable pre-game predictors. Excluding outcome fields prevents the model from learning information that would not exist when a future prediction is made.
"""
)

md(
    """
### Visualization 1 — Missing values by attribute

The following bar chart shows the 15 columns with the highest missing rates. This makes unusable attributes and less severe early-history gaps visible instead of hiding them inside an overall average.
"""
)
code(
    """
missing_pct = (100 * df.isna().mean()).sort_values(ascending=False).head(15)
plt.figure(figsize=(10, 6))
sns.barplot(x=missing_pct.values, y=missing_pct.index, color="#4472C4")
plt.title("Visualization 1: Attributes with the most missing data")
plt.xlabel("Missing values (%)")
plt.ylabel("Attribute")
plt.xlim(0, 105)
plt.tight_layout()
plt.show()
"""
)
md(
    """
**Inference:** Nine skater-summary columns are 100% missing and must be removed. After those fields, the largest missing rate is only about 3.3%, so median imputation fitted on the training period is more appropriate than discarding thousands of otherwise usable games.
"""
)

md(
    """
### Visualization 2 — Target class balance

This chart counts home wins and away wins and labels each bar with its percentage. It checks whether the classification target is severely imbalanced.
"""
)
code(
    """
target_counts = df[TARGET].value_counts().sort_index()
target_labels = ["Away win (0)", "Home win (1)"]

ax = sns.barplot(x=target_labels, y=target_counts.values, hue=target_labels, palette=["#C0504D", "#4F81BD"], legend=False)
for index, count in enumerate(target_counts.values):
    ax.text(index, count + 120, f"{count:,}\\n({count / len(df):.1%})", ha="center")
plt.title("Visualization 2: Home-win target distribution")
plt.xlabel("")
plt.ylabel("Games")
plt.ylim(0, target_counts.max() * 1.13)
plt.tight_layout()
plt.show()
"""
)
md(
    """
**Inference:** Home teams won 11,125 games (54.0%) and away teams won 9,466 games (46.0%). This is a mild home-ice imbalance, not an extreme class-imbalance problem, but stratification or time-aware class checks are still useful during validation.
"""
)

md(
    """
### Visualization 3 — Number of games by season

This chart counts observations in each season. It checks historical coverage and highlights seasons with unusually few games, which may reflect shortened schedules or incomplete periods.
"""
)
code(
    """
games_by_season = df.groupby("season").size()
season_labels = [f"{str(season)[:4]}–{str(season)[-2:]}" for season in games_by_season.index]

plt.figure(figsize=(12, 5))
sns.barplot(x=season_labels, y=games_by_season.values, color="#70AD47")
plt.title("Visualization 3: Games represented in each season")
plt.xlabel("Season")
plt.ylabel("Games")
plt.xticks(rotation=45, ha="right")
plt.tight_layout()
plt.show()
"""
)
md(
    """
**Inference:** Most full seasons contain a similar number of games, while shortened seasons contain fewer observations. Because the data covers many different seasons, performance should be tested on later games rather than assuming every season follows exactly the same distribution.
"""
)

md(
    """
### Visualization 4 — Home and away goal distributions

The next plot compares final home and away goal distributions. Scores are used here only for EDA and are not included as predictors, because final scores are unknown before a game.
"""
)
code(
    """
score_plot = df[["home_score", "away_score"]].rename(
    columns={"home_score": "Home goals", "away_score": "Away goals"}
).melt(var_name="Location", value_name="Goals")

plt.figure(figsize=(10, 5))
sns.histplot(
    data=score_plot,
    x="Goals",
    hue="Location",
    discrete=True,
    multiple="dodge",
    shrink=0.8,
    palette=["#4F81BD", "#C0504D"],
)
plt.title("Visualization 4: Distribution of home and away goals")
plt.xlim(-0.5, 10.5)
plt.xlabel("Goals scored")
plt.ylabel("Games")
plt.tight_layout()
plt.show()
"""
)
md(
    """
**Inference:** Both scoring distributions are right-skewed, but the home distribution is shifted slightly higher. Home teams averaged about 0.25 more goals per game, which is consistent with the 54.0% home-win rate.
"""
)

md(
    """
### Visualization 5 — Scoring trend by season

This line chart calculates average home and away goals separately for every season. It checks whether the scoring environment changes over time, which matters when older games are used to predict newer games.
"""
)
code(
    """
season_scoring = df.groupby("season")[["home_score", "away_score"]].mean().rename(
    columns={"home_score": "Home goals", "away_score": "Away goals"}
)
season_scoring.index = [f"{str(season)[:4]}–{str(season)[-2:]}" for season in season_scoring.index]

season_scoring.plot(marker="o", figsize=(12, 5), color=["#4F81BD", "#C0504D"])
plt.title("Visualization 5: Average scoring by season")
plt.xlabel("Season")
plt.ylabel("Average goals per team per game")
plt.xticks(range(len(season_scoring)), season_scoring.index, rotation=45, ha="right")
plt.legend(title="")
plt.tight_layout()
plt.show()
"""
)
md(
    """
**Inference:** Average scoring is not constant across the 16 seasons, although home teams generally remain above away teams. This time variation supports using chronological validation and recent-form features instead of randomly mixing all seasons.
"""
)

md(
    """
### Visualization 6 — Home-win rate by season

This chart calculates the target average in each season; because the target is 0 or 1, its average is the home-win percentage. It checks whether the strength of home-ice advantage changes over time.
"""
)
code(
    """
home_win_by_season = 100 * df.groupby("season")[TARGET].mean()
season_labels = [f"{str(season)[:4]}–{str(season)[-2:]}" for season in home_win_by_season.index]

plt.figure(figsize=(12, 5))
sns.lineplot(x=season_labels, y=home_win_by_season.values, marker="o", color="#8064A2")
plt.axhline(100 * df[TARGET].mean(), color="black", linestyle="--", label="Overall average")
plt.title("Visualization 6: Home-win percentage by season")
plt.xlabel("Season")
plt.ylabel("Home wins (%)")
plt.xticks(rotation=45, ha="right")
plt.legend()
plt.tight_layout()
plt.show()
"""
)
md(
    """
**Inference:** Home-win percentage varies around the overall 54.0% rate rather than staying fixed. A model evaluated only with a random split could hide this season-to-season change, while a later-period test set measures the real future-prediction problem.
"""
)

md(
    """
### Visualization 7 — Rest advantage and home-win rate

This block groups the home-minus-away rest-day difference into practical bins and plots the observed home-win percentage. Binning reduces noise and makes the direction of the relationship easier to interpret.
"""
)
code(
    """
rest_bins = [-np.inf, -3, -2, -1, 0, 1, 2, 3, np.inf]
rest_labels = ["≤ -3", "-2", "-1", "0", "+1", "+2", "+3", "≥ +4"]
rest_analysis = df.assign(
    rest_group=pd.cut(df["rest_days_diff"], bins=rest_bins, labels=rest_labels)
).groupby("rest_group", observed=True)[TARGET].agg(["mean", "count"])

plt.figure(figsize=(10, 5))
sns.barplot(x=rest_analysis.index, y=100 * rest_analysis["mean"], color="#F2A900")
plt.axhline(100 * df[TARGET].mean(), color="black", linestyle="--", label="Overall average")
plt.title("Visualization 7: Home-win rate by rest-day advantage")
plt.xlabel("Home rest days minus away rest days")
plt.ylabel("Home wins (%)")
plt.legend()
plt.tight_layout()
plt.show()

display(rest_analysis.rename(columns={"mean": "home_win_rate", "count": "games"}))
"""
)
md(
    """
**Inference:** A modest rest advantage is associated with a higher home-win rate: games where the home team had one or two extra rest days were won by the home team about 57% of the time. Extreme rest categories contain far fewer games, so their rates are less stable and should not be overinterpreted.
"""
)

md(
    """
### Visualization 8 — Elo advantage and home-win rate

This block divides pre-game Elo difference into ten equally sized groups, then plots the target average in each group. It tests whether stronger pre-game team ratings are associated with a greater chance of a home win.
"""
)
code(
    """
elo_analysis = df.assign(
    elo_decile=pd.qcut(df["elo_diff"], q=10, duplicates="drop")
).groupby("elo_decile", observed=True).agg(
    mean_elo_diff=("elo_diff", "mean"),
    home_win_rate=(TARGET, "mean"),
    games=(TARGET, "size"),
).reset_index(drop=True)

plt.figure(figsize=(10, 5))
sns.lineplot(data=elo_analysis, x="mean_elo_diff", y=elo_analysis["home_win_rate"] * 100, marker="o", color="#4F81BD")
plt.title("Visualization 8: Home-win rate across Elo-difference deciles")
plt.xlabel("Average home-minus-away Elo difference")
plt.ylabel("Home wins (%)")
plt.tight_layout()
plt.show()

display(elo_analysis)
"""
)
md(
    """
**Inference:** The relationship is strong and orderly: the home-win rate rises from about 39% in the lowest Elo-difference group to about 71% in the highest. Elo difference is therefore a useful pre-game predictor, although the remaining uncertainty shows that it cannot determine every game by itself.
"""
)

md(
    """
### Visualization 9 — Elo distribution by game outcome

This box plot compares pre-game Elo differences for home wins and away wins. It shows both the typical difference between the two outcome groups and the large overlap that remains.
"""
)
code(
    """
elo_outcome = df.assign(
    outcome=df[TARGET].map({0: "Away win", 1: "Home win"})
)

plt.figure(figsize=(9, 5))
sns.boxplot(
    data=elo_outcome,
    x="outcome",
    y="elo_diff",
    hue="outcome",
    palette={"Away win": "#C0504D", "Home win": "#4F81BD"},
    legend=False,
    showfliers=False,
)
plt.axhline(0, color="black", linestyle="--", linewidth=1)
plt.title("Visualization 9: Pre-game Elo difference by outcome")
plt.xlabel("")
plt.ylabel("Home Elo minus away Elo")
plt.tight_layout()
plt.show()
"""
)
md(
    """
**Inference:** Home wins tend to have higher pre-game Elo differences than away wins, but the boxes overlap substantially. This confirms that Elo contributes predictive signal without being sufficient as a single-variable decision rule.
"""
)

md(
    r"""
## 1. What is the Pearson correlation coefficient?

The **Pearson correlation coefficient**, written as $r$, measures the direction and strength of the **linear** relationship between two numerical variables:

$$
r = \frac{\operatorname{cov}(X,Y)}{s_Xs_Y}
$$

Its value ranges from $-1$ to $+1$:

- $r$ near $+1$: strong positive linear relationship.
- $r$ near $-1$: strong negative linear relationship.
- $r$ near $0$: little or no linear relationship.

For this project, `target_home_win` is binary. Pearson correlation between a numerical predictor and a binary target is equivalent to a point-biserial correlation. A positive value means larger predictor values are associated with home wins; a negative value means larger values are associated with away wins. Correlation does not prove causation and may miss nonlinear relationships or interactions.
"""
)

md(
    """
## 2. How is each attribute important for predicting the target (heat map)?

### Visualization 10 — Pearson-correlation heat map

The next block calculates each selected pre-game attribute's Pearson correlation with the target, sorts attributes by absolute correlation, and displays a one-column heat map. The accompanying table reports every selected attribute, its signed correlation, its absolute screening importance, and the direction of its relationship. This is filter-based feature importance, not causal or final model-based importance.
"""
)
code(
    """
correlations = modeling_df[pregame_features].corrwith(modeling_df[TARGET])
correlation_table = (
    correlations.rename("pearson_r")
    .to_frame()
    .assign(abs_importance=lambda table: table["pearson_r"].abs())
    .sort_values("abs_importance", ascending=False)
)
correlation_table["direction"] = np.select(
    [correlation_table["pearson_r"] > 0, correlation_table["pearson_r"] < 0],
    ["Positive: higher values favor a home win", "Negative: higher values favor an away win"],
    default="No linear direction",
)

plt.figure(figsize=(8, 12))
sns.heatmap(
    correlation_table[["pearson_r"]],
    cmap="RdBu",
    center=0,
    vmin=-0.20,
    vmax=0.20,
    annot=True,
    fmt=".3f",
    linewidths=0.5,
    cbar_kws={"label": "Pearson correlation (r)"},
)
plt.title("Visualization 10: Pre-game attribute relationships with target_home_win")
plt.xlabel("Target")
plt.ylabel("Pre-game attribute")
plt.tight_layout()
plt.show()

display(correlation_table)
"""
)
md(
    """
**Inference:** `elo_diff` is the strongest selected linear predictor ($r=+0.179$), followed by the recency-weighted goal-difference gap ($r=+0.156$), even-strength shot-attempt-share gap ($r=+0.144$), and recency-weighted win-rate gap ($r=+0.144$). Positive scoring, possession, and rating advantages favor a home win. Negative correlations for attempts or shots against mean that allowing more activity than the opponent reduces the home team's win tendency.

All absolute correlations are modest. Therefore, no attribute predicts the target well by itself; a model should combine several predictors and may benefit from nonlinear relationships and interactions. Highly related attributes should also be checked for redundancy. For final feature selection, correlations must be recalculated using only the training data so that the test set remains unseen.
"""
)

md(
    """
## 3. What is k-fold cross-validation?

K-fold cross-validation is a resampling method used to estimate how well a model will generalize to unseen data. The training data is divided into $k$ approximately equal groups called folds. The model is trained $k$ times. Each run uses one fold for validation and the other $k-1$ folds for training, so every observation is used for validation once and for training $k-1$ times. The validation scores are averaged, and their variation shows how stable performance is across folds.

For example, 5-fold cross-validation trains on about 80% of the development data and validates on about 20% in each of five runs. Common choices are $k=5$ or $k=10$. For classification, stratified k-fold is often used to keep class proportions similar. Imputation, scaling, feature selection, and tuning must be fitted inside each training fold to prevent leakage.

Because NHL games are chronological, ordinary shuffled k-fold is not suitable for the final evaluation. A time-series or rolling-origin version should train on earlier games and validate on later games so future results never influence past predictions.
"""
)

md(
    """
## 4. Why is the training dataset 70–80%? Why is the test dataset 20–30%?

A **70–80% training share** gives the model enough observations to learn stable patterns, estimate parameters, and represent less common situations. If the training portion is too small, the fitted model may have high variance or fail to learn useful relationships.

A **20–30% test share** leaves enough completely unseen observations for a reliable estimate of generalization. A very small test set can produce an unstable performance estimate because a few predictions have too much influence. A very large test set wastes data that could improve training.

Therefore, 70/30 and 80/20 are practical compromises, not strict rules. The test set must remain untouched until final evaluation, and cross-validation should occur only inside the training set. For NHL prediction, the split should respect time: earlier games are training data and the latest games are test data.

### Apply the chronological 80/20 split

This code uses the earliest 80% of games for training and the latest 20% for testing. It then fits median imputation values on the training period only and applies them to both sets. Finally, it ranks attributes using training-only correlations and retains the 15 strongest non-empty predictors as a transparent Phase 2 feature-selection step.
"""
)
code(
    """
split_index = int(len(modeling_df) * 0.80)
train_df = modeling_df.iloc[:split_index].copy()
test_df = modeling_df.iloc[split_index:].copy()

X_train = train_df[pregame_features].copy()
y_train = train_df[TARGET].astype(int).copy()
X_test = test_df[pregame_features].copy()
y_test = test_df[TARGET].astype(int).copy()

# Learn replacement values from training data only.
training_medians = X_train.median(numeric_only=True)
X_train = X_train.fillna(training_medians)
X_test = X_test.fillna(training_medians)

# Select features using only the training period; the test target is never consulted.
training_correlations = X_train.corrwith(y_train).abs().sort_values(ascending=False)
selected_features = training_correlations.head(15).index.tolist()
X_train_selected = X_train[selected_features]
X_test_selected = X_test[selected_features]

split_summary = pd.DataFrame(
    {
        "rows": [len(X_train_selected), len(X_test_selected)],
        "share": [len(X_train_selected) / len(modeling_df), len(X_test_selected) / len(modeling_df)],
        "start_date": [train_df["game_date"].min().date(), test_df["game_date"].min().date()],
        "end_date": [train_df["game_date"].max().date(), test_df["game_date"].max().date()],
        "home_win_rate": [y_train.mean(), y_test.mean()],
        "missing_after_imputation": [int(X_train_selected.isna().sum().sum()), int(X_test_selected.isna().sum().sum())],
    },
    index=["Training set", "Test set"],
)

display(split_summary)
print("Selected training-only features:")
display(training_correlations.loc[selected_features].rename("absolute_training_correlation").to_frame())
"""
)
md(
    """
**Inference:** The chronological split assigns 16,472 games to training (80.0%) and 4,119 to testing (20.0%). Both selected matrices contain no missing values after training-only median imputation. The test period is later than the training period, and feature selection never uses the test target, so the setup is suitable for an honest future-game evaluation.
"""
)

nb["cells"] = cells
nbf.write(nb, OUTPUT)
print(f"Wrote {OUTPUT}")
