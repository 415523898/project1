"""Domain method registrations."""

from engine.methods.domain_meta import meta_analysis as meta_analysis
from engine.methods.domain_quality import capability as capability
from engine.methods.domain_quality import control_chart as control_chart
from engine.methods.domain_quality import weibull as weibull
from engine.methods.domain_survey import conjoint as conjoint
from engine.methods.domain_survey import kano as kano
from engine.methods.domain_survey import maxdiff as maxdiff
from engine.methods.domain_survey import nps as nps
from engine.methods.domain_survey import price_sensitivity as price_sensitivity
from engine.methods.domain_survey import reliability as reliability
from engine.methods.domain_survival import competing_risk as competing_risk
from engine.methods.domain_survival import cox as cox
from engine.methods.domain_survival import kaplan_meier as kaplan_meier
from engine.methods.domain_survival import nomogram as nomogram
from engine.methods.domain_text import lda_topic as lda_topic
from engine.methods.domain_text import sentiment as sentiment
from engine.methods.domain_text import tfidf as tfidf
from engine.methods.domain_text import wordfreq as wordfreq
from engine.registry import register as register

register("domain.wordfreq")(wordfreq)
register("domain.tfidf")(tfidf)
register("domain.sentiment")(sentiment)
register("domain.lda")(lda_topic)
register("domain.km")(kaplan_meier)
register("domain.cox")(cox)
register("domain.nomogram")(nomogram)
register("domain.competing")(competing_risk)
register("domain.reliability")(reliability)
register("domain.nps")(nps)
register("domain.kano")(kano)
register("domain.maxdiff")(maxdiff)
register("domain.conjoint")(conjoint)
register("domain.psm")(price_sensitivity)
register("domain.control")(control_chart)
register("domain.capability")(capability)
register("domain.weibull")(weibull)
register("domain.meta")(meta_analysis)
