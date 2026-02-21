# ssmsapp/migrations/000X_backfill_papers.py
from django.db import migrations

def create_papers(apps, schema_editor):
    Question = apps.get_model('ssmsapp', 'Question')
    QuestionPaper = apps.get_model('ssmsapp', 'QuestionPaper')

    # Group existing questions by (title, creator, dept_year_subject)
    groups = {}
    for q in Question.objects.exclude(title__isnull=True).exclude(title__exact=''):
        key = (q.title, q.created_by_id, q.dept_year_subject_id)
        groups.setdefault(key, []).append(q)

    for (title, user_id, dys_id), qs in groups.items():
        # create a paper for this group
        paper = QuestionPaper.objects.create(
            title=title,
            created_by_id=user_id,
            dept_year_subject_id=dys_id,
            num_questions=len(qs)
        )
        # attach each question to the new paper
        for q in qs:
            q.paper_id = paper.id
            q.save()

def reverse_func(apps, schema_editor):
    # optional: undo the backfill by detaching questions and deleting created papers
    Question = apps.get_model('ssmsapp', 'Question')
    QuestionPaper = apps.get_model('ssmsapp', 'QuestionPaper')

    # find papers that were created by this migration heuristic (no perfect marker,
    # so this reverse is conservative: detach papers that have same title and created_by)
    for paper in QuestionPaper.objects.all():
        # detach questions
        Question.objects.filter(paper_id=paper.id).update(paper=None)
        # optionally delete the paper (uncomment if you want)
        # paper.delete()

class Migration(migrations.Migration):

    dependencies = [
        ('ssmsapp', '0018_alter_question_created_at_questionpaper_and_more'),  # <-- replace with the actual previous migration name
    ]

    operations = [
        migrations.RunPython(create_papers, reverse_func),
    ]
