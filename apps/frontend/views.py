import re
from django.shortcuts import render, redirect
from django.contrib import messages

from .forms import DrugEvaluationForm
from medguard_app.orchestrator import get_decision_pipeline


def intro(request):
    """Landing/introduction page."""
    return render(request, 'intro.html')


def home(request):
    """Home page with drug evaluation form."""
    if request.method == 'POST':
        form = DrugEvaluationForm(request.POST)
        if form.is_valid():
            # Parse symptoms - handle both newline and comma separation
            symptoms_raw = form.cleaned_data['symptoms']
            symptoms = [
                s.strip()
                for s in re.split(r'[,\n]', symptoms_raw)
                if s.strip()
            ]

            # Parse existing medications
            existing_raw = form.cleaned_data.get('existing_medications', '')
            existing = [
                m.strip()
                for m in re.split(r'[,\n]', existing_raw)
                if m.strip()
            ] if existing_raw else []

            # Store in session
            request.session['symptoms'] = symptoms
            request.session['drug'] = form.cleaned_data['drug'].strip()
            request.session['existing'] = existing

            return redirect('result')
    else:
        form = DrugEvaluationForm()

    return render(request, 'home.html', {'form': form})


def result(request):
    """Results page showing drug evaluation."""
    # Get data from session
    symptoms = request.session.get('symptoms', [])
    drug = request.session.get('drug', '')
    existing = request.session.get('existing', [])

    # If no data in session, redirect to home
    if not drug:
        messages.warning(request, 'Please enter your medication details first.')
        return redirect('home')

    # Get the decision pipeline and evaluate
    pipeline = get_decision_pipeline()
    result = pipeline.evaluate(
        symptoms=symptoms,
        proposed_drug=drug,
        existing_drugs=existing
    )

    # Add the input data to the result for display
    result['input'] = {
        'symptoms': symptoms,
        'drug': drug,
        'existing_medications': existing,
    }

    return render(request, 'result.html', {'result': result})


def how_it_works(request):
    """How it works explainer page."""
    return render(request, 'how_it_works.html')
