from django import template
from django.utils.translation import gettext as _
from django.utils.translation import get_language
import re

register = template.Library()


def _is_ru_language():
    language = (get_language() or "").lower()
    return language.startswith("ru")

@register.filter
def split(value, arg):
    """String ni ajratish uchun filter"""
    if not value:
        return []
    return value.split(arg)

@register.filter
def get_first(value):
    """Listning birinchi elementini olish"""
    if value and len(value) > 0:
        return value[0]
    return ""

@register.filter
def get_last(value):
    """Listning oxirgi elementini olish"""
    if value and len(value) > 0:
        return value[-1]
    return ""

@register.filter
def translate_round_name(round_name):
    """
    Match round_name ni tarjima qilish va to'g'ri formatlash.
    Natija: "1-davra, 1-tur" (uz) yoki "1-й круг, 1-й тур" (ru)
    """
    if not round_name:
        return "Групповой этап" if _is_ru_language() else _("Guruh bosqichi")
    
    round_name = str(round_name).strip()
    
    # 1. Playoff bosqichlari (Aniq mos kelishini tekshiramiz)
    playoff_names = {
        "Final": _("Final"),
        "1/2 Final": _("1/2 Final"),
        "1/4 Final": _("1/4 Final"),
        "1/8 Final": _("1/8 Final"),
        "1/16 Final": _("1/16 Final"),
        "1/32 Final": _("1/32 Final"),
        "Round 1 (Play-in)": _("Round 1 (Play-in)"),
        "Round 1": _("Round 1"),
        "Round 2": _("Round 2"),
        "Round 3": _("Round 3"),
    }
    
    if round_name in playoff_names:
        return playoff_names[round_name]
    
    # 2. Guruh formati ("Guruh A" yoki "Group B")
    if ("Guruh" in round_name or "Group" in round_name) and "davra" not in round_name.lower():
        parts = round_name.split()
        if len(parts) >= 2:
            label = "Группа" if _is_ru_language() else _("Guruh")
            return f"{label} {parts[-1]}"
    
    normalized_name = round_name.lower()

    # 3. Liga formati ("1-davra, 1-tur" yoki ruscha/inglizcha variantlari)
    league_round_match = re.search(
        r"(\d+)\s*[- ]?\s*(?:davra|круг|round)\s*,\s*(\d+)\s*[- ]?\s*(?:tur|тур|tour|round)",
        normalized_name,
        flags=re.IGNORECASE,
    )
    if league_round_match:
        davra_num = league_round_match.group(1)
        tur_num = league_round_match.group(2)
        if _is_ru_language():
            return f"{davra_num}-й круг, {tur_num}-й тур"
        return _("%(d)s-davra, %(t)s-tur") % {"d": davra_num, "t": tur_num}

    # 4. Faqat tur formati ("1-tur" yoki "1-й тур")
    single_tur_match = re.search(
        r"(\d+)\s*[- ]?\s*(?:tur|тур|tour|round)",
        normalized_name,
        flags=re.IGNORECASE,
    )
    if single_tur_match:
        tur_num = single_tur_match.group(1)
        if _is_ru_language():
            return f"{tur_num}-й тур"
        return _("%(t)s-tur") % {"t": tur_num}
    
    return round_name

@register.filter
def get_round_number(round_name, part_type):
    """Round name dan raqamni olish"""
    if not round_name:
        return ""
    
    if part_type == 'davra' and "davra" in round_name:
        try:
            if "-davra" in round_name:
                return round_name.split("-davra")[0].strip()
            elif "davra" in round_name:
                if "-" in round_name:
                    return round_name.split("-")[0]
        except:
            pass
    elif part_type == 'tur' and "tur" in round_name:
        try:
            if "-tur" in round_name:
                return round_name.split("-tur")[0].strip()
            elif "tur" in round_name and "," in round_name:
                parts = round_name.split(",")
                if len(parts) > 1:
                    tur_part = parts[1].strip()
                    if "-" in tur_part:
                        return tur_part.split("-")[0]
        except:
            pass
    
    return ""


@register.filter
def format_league_round(round_name):
    """Liga round_name ni to'g'ri formatda qaytarish"""
    if not round_name:
        return ""
    
    if "davra" in round_name and "tur" in round_name and "," in round_name:
        try:
            davra_tur = round_name.split(",")
            if len(davra_tur) == 2:
                davra = davra_tur[0].strip()
                tur = davra_tur[1].strip()
                
                if "-" in davra:
                    davra_num = davra.split("-")[0]
                else:
                    davra_num = davra.replace("davra", "").strip()
                
                if "-" in tur:
                    tur_num = tur.split("-")[0]
                else:
                    tur_num = tur.replace("tur", "").strip()
                
                return f"{davra_num}-{_('davra')}, {tur_num}-{_('tur')}"
        except:
            pass
    
    return round_name
