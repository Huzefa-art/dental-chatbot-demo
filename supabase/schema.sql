-- Dental demo chatbot -- Supabase schema
-- Run this in the Supabase SQL editor (Project > SQL Editor > New query) once, on project creation.

create table if not exists clinics (
  slug text primary key,
  practice_name text not null,
  doctors text[] default '{}',
  address text,
  phone text,
  hours text,
  booking_note text,
  services text[] default '{}',
  insurance_and_financing text[] default '{}',
  affiliations text[] default '{}',
  social jsonb default '{}',
  system_prompt_extra text,
  created_at timestamptz default now()
);

create table if not exists conversations (
  id uuid primary key default gen_random_uuid(),
  session_id text unique not null,
  clinic_slug text references clinics(slug),
  lead_name text,
  lead_phone text,
  preferred_time text,
  patient_type text,        -- 'new' / 'existing' / null (unresolved)
  reason_for_visit text,    -- 'routine_cleaning' / 'pain_emergency' / 'cosmetic' / 'pricing' / 'browsing' / null
  referral_source text,     -- 'search' / 'referral' / 'social_media' / 'ad' / 'other' / null
  request_type text check (request_type in ('booking', 'callback_request', 'general_inquiry')),
  transcript jsonb default '[]',
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

-- Idempotent for already-deployed projects: create table if not exists above won't add columns
-- to a table that already exists, so add them explicitly too.
alter table conversations add column if not exists patient_type text;
alter table conversations add column if not exists reason_for_visit text;
alter table conversations add column if not exists referral_source text;
alter table conversations add column if not exists request_type text
  check (request_type in ('booking', 'callback_request', 'general_inquiry'));

-- keep updated_at fresh on every row update
create or replace function set_updated_at() returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

drop trigger if exists conversations_updated_at on conversations;
create trigger conversations_updated_at
  before update on conversations
  for each row execute function set_updated_at();

-- Row Level Security: enabled with permissive read/write for the service_role key used by the
-- backend. If you later expose Supabase directly to a browser client, tighten these policies.
alter table clinics enable row level security;
alter table conversations enable row level security;

create policy "service role full access on clinics" on clinics
  for all using (true) with check (true);
create policy "service role full access on conversations" on conversations
  for all using (true) with check (true);

-- Seed: Hiner Family Dentistry (matches clinics/hiner_family_dentistry.json)
insert into clinics (
  slug, practice_name, doctors, address, phone, hours, booking_note,
  services, insurance_and_financing, affiliations, social, system_prompt_extra
) values (
  'hiner_family_dentistry',
  'Hiner Family Dentistry',
  array['Dr. Matthew Hiner, DDS', 'Dr. Reagan Hiner, DDS (husband and wife)'],
  '8811 Frankway Dr, Suite D, Houston, TX 77096',
  '(713) 667-6478',
  'Monday-Thursday, 8:00 AM - 4:00 PM. Closed Friday-Sunday. Same-day/extended-hours appointments available by calling.',
  'Online scheduler available, or call directly. No AI chatbot or 24/7 booking currently exists on their site.',
  array[
    'Preventive care: checkups & cleanings',
    'Children''s dentistry (family-friendly, all ages)',
    'Gum disease treatment',
    'Restorative: crowns, fillings',
    'Missing teeth solutions: bridges, dental implants, dentures',
    'Cosmetic dentistry: veneers, Botox, teeth whitening',
    'Orthodontics',
    'Emergency dentistry (pain/urgent issues)',
    'Wisdom teeth removal'
  ],
  array[
    'Accepts many dental insurance plans',
    'In-house membership plans for uninsured patients',
    'Low-to-no interest financing available'
  ],
  array['American Dental Association (ADA)', 'American Academy of Cosmetic Dentistry (AACD)', 'Texas Dental Association'],
  '{"facebook": "facebook.com/HinerDentistry", "instagram": "instagram.com/hinerfamilydentistry"}'::jsonb,
  'If the user mentions pain, an emergency, or urgent issue, tell them to call (713) 667-6478 directly, and still collect their name and phone number so the team can follow up first thing when the office opens if it''s after hours. Always offer to collect name, phone, and preferred appointment time for any booking request, and tell them the team will confirm by phone.'
)
on conflict (slug) do nothing;
