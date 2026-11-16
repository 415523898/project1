"""Shared teaching source constructors; no algorithm imports or lesson registry."""


def source(title, url, section):
    return {"title": title, "url": url, "section": section}


def scipy(name, section="Notes: statistic and null distribution"):
    return source(
        "SciPy · " + name,
        f"https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.{name}.html",
        section,
    )


def sklearn(page, section):
    path, _, anchor = page.partition("#")
    return source(
        "scikit-learn · " + section,
        f"https://scikit-learn.org/stable/modules/{path}.html" + (f"#{anchor}" if anchor else ""),
        section,
    )


def sm(path, section):
    page, _, anchor = path.partition("#")
    return source(
        "statsmodels · " + section,
        f"https://www.statsmodels.org/stable/{page}.html" + (f"#{anchor}" if anchor else ""),
        section,
    )


PANDAS = source(
    "pandas · 缺失数据",
    "https://pandas.pydata.org/docs/user_guide/missing_data.html",
    "Filling missing data; interpolation; dropping missing data",
)


PREPROCESS = sklearn(
    "preprocessing", "Standardization; scaling; encoding categorical features; power transforms"
)


PCA = sklearn("decomposition#pca", "PCA: centered data, singular values and explained variance")


ENSEMBLE = sklearn(
    "ensemble", "Random forests; averaging class probabilities; gradient boosting; AdaBoost"
)


DID = source(
    "Cunningham · Difference-in-Differences",
    "https://mixtape.scunning.com/09-difference_in_differences",
    "Four averages and three subtractions; identification assumptions",
)


DESIGN = source(
    "NIST/SEMATECH · Process improvement",
    "https://www.itl.nist.gov/div898/handbook/pri/pri.htm",
    "5.3 Choosing an experimental design; 5.4 Modeling and optimization",
)


QUALITY = source(
    "NIST/SEMATECH · Process monitoring",
    "https://www.itl.nist.gov/div898/handbook/pmc/pmc.htm",
    "Control charts and process capability",
)


TOPSIS = source(
    "Hwang & Yoon (1981) · Multiple Attribute Decision Making",
    "https://doi.org/10.1007/978-3-642-48318-9",
    "Chapter 2: entropy weights; Chapter 3: TOPSIS",
)
