/**
 * Legrand GeoAI — Types TypeScript.
 */

// --- Auth ---
export interface LoginRequest {
  email: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: "admin" | "user" | "viewer";
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

// --- Collections ---
export interface Collection {
  id: string;
  name: string;
  description: string | null;
  chroma_collection_name: string;
  owner_id: string;
  document_count: number;
  created_at: string;
  updated_at: string;
}

export interface CollectionCreate {
  name: string;
  description?: string;
}

// --- Documents ---
export interface Document {
  id: string;
  filename: string;
  original_filename: string;
  mime_type: string;
  file_size: number;
  status: "pending" | "processing" | "completed" | "failed";
  page_count: number | null;
  chunk_count: number | null;
  ocr_method: string | null;
  error_message: string | null;
  sub_status: string | null;
  progress: number | null;
  workflow_run_id: string | null;
  collection_id: string;
  collection_name: string | null;
  uploaded_by: string;
  uploader_name: string | null;
  created_at: string;
  updated_at: string;
}

// --- Chat ---
export interface ChatSession {
  id: string;
  title: string;
  collection_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources: SourceInfo[] | null;
  model_name: string | null;
  tokens_used: number | null;
  created_at: string;
}

export interface ChatSessionDetail extends ChatSession {
  messages: ChatMessage[];
}

export interface SourceInfo {
  filename: string;
  chunk_index: number;
  page_numbers: number[];
  document_id: string;
  score: number;
}

export interface ChatQueryRequest {
  message: string;
  collection_id: string;
  session_id?: string;
}

// --- Pagination ---
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  size: number;
  pages: number;
}

// --- Common ---
export interface MessageResponse {
  message: string;
}
