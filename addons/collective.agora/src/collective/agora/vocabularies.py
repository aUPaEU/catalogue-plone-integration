from zope.schema.vocabulary import SimpleTerm, SimpleVocabulary


def frequencies(context):
    return SimpleVocabulary((
        SimpleTerm('minute', title='Every minute'),
        SimpleTerm('hour', title='Every hour'),
        SimpleTerm('day', title='Once a day'),
    ))
