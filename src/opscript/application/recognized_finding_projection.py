from opscript.models import RecognizedFinding, RecognitionResult


def recognized_finding_from_recognition(
    recognition_result: RecognitionResult,
) -> RecognizedFinding:
    return RecognizedFinding(recognition_result=recognition_result)
