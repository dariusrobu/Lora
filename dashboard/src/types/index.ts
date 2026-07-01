export interface Task {
  id: number
  title: string
  notes?: string
  priority: "high" | "medium" | "low"
  status: "pending" | "done"
  due_date?: string
  project_id?: number
  project_name?: string
  created_at: string
}

export interface ProjectTask {
  id: number
  title: string
  status: string
  priority: string
  due_date?: string
}

export interface ProjectNote {
  id: number
  content: string
  type?: string
  created_at: string
}

export interface Project {
  id: number
  name: string
  description?: string
  status: string
  priority: string
  deadline?: string
  category?: string
  progress_pct?: number
  task_count?: number
  completed_tasks?: number
  pending_tasks?: number
  overdue_tasks?: number
  created_at: string
  tasks?: ProjectTask[]
  notes?: ProjectNote[]
}

export interface Transaction {
  id: number
  amount: number
  category: string
  description: string
  type: "expense" | "income"
  transaction_date: string
}

export interface FinanceSummary {
  income: number
  expense: number
  balance: number
}

export interface ShoppingItem {
  id: number
  item: string
  category?: string
  is_bought: boolean
}

export interface MemoryFact {
  id: number
  fact: string
  category: string
  confidence: number
  created_at: string
}

export interface Note {
  id: number
  title: string
  body: string
  tags?: string[]
  is_pinned: boolean
  created_at: string
}

export interface Skill {
  id: number
  name: string
  level: number
  xp: number
  streak: number
}

export interface GoalTask {
  id: number
  title: string
  is_completed: boolean
}

export interface Goal {
  id: number
  title: string
  description?: string
  category?: string
  deadline?: string
  progress: number
  time_horizon: string
  status: string
  total_tasks?: number
  completed_tasks?: number
  tasks?: GoalTask[]
}

export interface Book {
  id: number
  title: string
  author?: string
  total_pages?: number
  pages_read: number
  status: string
  rating?: number
}

export interface Meal {
  id: number
  meal_type: string
  description: string
  calories: number
  protein: number
  carbs: number
  fat: number
}

export interface NutritionTargets {
  calories: number
  protein_g: number
  carbs_g: number
  fat_g: number
}

export interface NutritionResponse {
  meals: Meal[]
  totals: { calories: number; protein: number; carbs: number; fat: number }
  targets?: NutritionTargets
  weekHistory?: { date: string; calories: number }[]
}

export interface WorkoutExercise {
  name: string
  sets?: number
  reps?: number
  weight_kg?: number
}

export interface WorkoutSession {
  id: number
  workout_date: string
  sport_id?: number
  type: string
  icon?: string
  duration_min: number
  calories?: number
  notes?: string
  exercises?: WorkoutExercise[]
}

export interface WorkoutStats {
  total_sessions: number
  active_days: number
  most_common_type: string | null
  avg_duration: number | null
}

export interface PersonalRecord {
  exercise_name: string
  max_weight: number
}

export interface WorkoutResponse {
  stats: WorkoutStats
  recent: WorkoutSession[]
  personal_records: PersonalRecord[]
}

export interface UniversitySubject {
  id: number
  name: string
  professor?: string
  credits?: number
  attendance_pct?: number
  grade?: number
}

export interface TravelList {
  [listName: string]: TravelItem[]
}

export interface TravelItem {
  id: number
  item: string
  is_packed: boolean
  list_name?: string
  category?: string
  trip_type?: string
}

export interface Profile {
  id: number
  name: string
  tone: string
  timezone: string
  morning_time?: string
  eod_time?: string
  preferred_tone?: string
  active_hours_start?: string
  active_hours_end?: string
  university_name?: string
  faculty?: string
  specialization?: string
  study_year?: number
  study_group?: string
  water_target_ml?: number
  personal_notes?: string
  llm_provider?: string
  llm_host?: string
  llm_model?: string
  gemini_api_key?: string
  city_name?: string
  latitude?: number
  longitude?: number
  is_at_home?: boolean
  home_latitude?: number
  home_longitude?: number
  preferred_tone?: string
  units?: string
  language?: string
  week_start_day?: string
  currency?: string
  dietary_preferences?: string
  notification_config?: Record<string, any>
  created_at?: string
  updated_at?: string
}

export interface MoodEntry {
  mood: string
  count?: number
  date?: string
}

export interface HealthLog {
  log_date: string
  sleep_hours?: number
  sleep_quality?: string
  water_ml?: number
  nutrition?: string
  weight_kg?: number
  cigarettes?: number
  notes?: string
}

export interface HealthSummary {
  avg_sleep?: number
  common_sleep_quality?: string
  avg_water?: number
  avg_cigarettes?: number
  total_cigarettes?: number
  min_weight?: number
  max_weight?: number
  good_nutrition_days?: number
  total_days?: number
  weight_trend?: string
  recent_weight?: number
  prev_weight?: number
}

export interface HealthResponse {
  summary: HealthSummary
  history: HealthLog[]
}

export interface CalendarEvent {
  id: number
  title: string
  description?: string
  event_date: string
  event_time?: string
  event_type: string
}

export interface CalendarScheduleEntry {
  id: number
  subject_name: string
  start_time: string
  end_time: string
  room?: string
  class_type?: string
}

export interface CalendarDay {
  date: string
  day_name: string
  events: CalendarEvent[]
  schedule: CalendarScheduleEntry[]
}

// ---- Phase 3 types ----

export interface JobConfig {
  job_name: string
  enabled: boolean
  cron_time?: string
  last_run?: string
  last_duration_ms?: number
  last_error?: string
  created_at: string
  updated_at: string
}

export interface LogStats {
  total: number
  errors: number
  success_rate: number
  by_module: { module: string; total: number; errors: number }[]
  top_errors: { error_message: string; count: number }[]
}

export interface LogEntry {
  id: number
  intent: string
  module: string
  success: boolean
  error_type?: string
  error_message?: string
  created_at: string
}

export interface LogResponse {
  total: number
  offset: number
  limit: number
  entries: LogEntry[]
}

export interface CalendarSyncStatus {
  total_synced: number
  by_type: { lora_type: string; count: number }[]
  last_sync?: { synced_at: string; lora_type: string; lora_id: number; summary: string } | null
  recent_errors: any[]
}

export interface BackupConfig {
  id?: number
  enabled: boolean
  schedule_cron: string
  retention_days: number
  last_backup_at?: string
  next_backup_at?: string
}

export interface BackupRecord {
  id: number
  status: string
  file_name?: string
  file_size_bytes?: number
  error_message?: string
  started_at: string
  completed_at?: string
  created_at: string
}
