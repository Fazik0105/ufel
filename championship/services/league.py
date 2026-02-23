from ..models import Match

def generate_league_matches(championship, users):
    Match.objects.filter(championship=championship).delete()

    matches = []
    for i in range(len(users)):
        for j in range(i + 1, len(users)):
            matches.append(
                Match(
                    championship=championship,
                    home_user=users[i],
                    away_user=users[j]
                )
            )
    Match.objects.bulk_create(matches)
