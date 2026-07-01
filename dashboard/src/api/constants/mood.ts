export const MOODS = ["great", "good", "okay", "meh", "bad"] as const
export type Mood = typeof MOODS[number]

export const MOOD_EMOJI: Record<string, string> = {
  great: "😄", good: "🙂", okay: "😐", meh: "😕", bad: "😢",
}

export const MOOD_SCORE: Record<string, number> = {
  great: 5, good: 4, okay: 3, meh: 2, bad: 1,
}
