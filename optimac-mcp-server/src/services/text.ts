/**
 * Text processing utilities shared across bridge tools.
 */

/**
 * Strip markdown code fences from model output.
 * Handles: single fence, multiple fences, surrounding text, CRLF, missing language tag.
 */
export function stripCodeFences(text: string): string {
    const trimmed = text.trim();

    // Single complete fence block (with possible surrounding text)
    const singleFence = trimmed.match(/```\w*\r?\n([\s\S]*?)\r?\n```/);
    if (singleFence) {
        // Check if there are multiple fence blocks
        const allFences = [...trimmed.matchAll(/```\w*\r?\n([\s\S]*?)\r?\n```/g)];
        if (allFences.length > 1) {
            return allFences.map((m) => m[1]).join("\n\n");
        }
        return singleFence[1];
    }

    return text;
}

/**
 * Basic quality heuristics for model output.
 * Returns a quality assessment with a pass/fail verdict and reasons.
 */
export function assessResponseQuality(
    response: string,
    minLength = 10
): { ok: boolean; reasons: string[] } {
    const reasons: string[] = [];
    const trimmed = response.trim();

    // Too short
    if (trimmed.length <= minLength) {
        reasons.push(`response_too_short: ${trimmed.length} chars (min ${minLength})`);
    }

    // Empty or whitespace-only
    if (!trimmed) {
        reasons.push("empty_response");
        return { ok: false, reasons };
    }

    // Common refusal/error patterns
    const refusalPatterns = [
        /^i('m| am) (sorry|unable|not able)/i,
        /^i can('t|not) (help|assist|do|provide)/i,
        /^(error|undefined|null|nan)$/i,
        /^as an ai/i,
    ];
    for (const pattern of refusalPatterns) {
        if (pattern.test(trimmed)) {
            reasons.push("detected_refusal_or_error");
            break;
        }
    }

    // Repetition check: split into 3-word chunks and check unique ratio
    const words = trimmed.split(/\s+/);
    if (words.length >= 15) {
        const trigrams = new Set<string>();
        let totalTrigrams = 0;
        for (let i = 0; i <= words.length - 3; i++) {
            trigrams.add(words.slice(i, i + 3).join(" ").toLowerCase());
            totalTrigrams++;
        }
        const uniqueRatio = trigrams.size / totalTrigrams;
        if (uniqueRatio < 0.3) {
            reasons.push(`high_repetition: ${Math.round(uniqueRatio * 100)}% unique trigrams`);
        }
    }

    return { ok: reasons.length === 0, reasons };
}
