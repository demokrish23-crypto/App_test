# Faculty Dashboard - Complete Flow Guide

## Main Dashboard Features

### 1. Dashboard (`/faculty/dashboard`)
- Welcome message with user name
- 4 Key Performance Indicators:
  - Total Questions in Bank
  - Papers Generated
  - Unique Subjects
  - Average Difficulty
- Quick Action Cards:
  - Generate Paper
  - Add Questions
  - View History
  - Analytics
- Quick Start Guide

### 2. Paper Generator Flow (`/faculty/paper-generator`)
**Step 1: Input Details**
- Subject Name (required)
- Syllabus Topics (required) - one topic per line
- Question Types (required) - checkboxes for 2/4/8 marks
- Difficulty Level (1-5 slider)
- Submit button

**Processing:**
- Validates all inputs
- Parses topics from syllabus
- Generates questions using Bloom's taxonomy
- Creates Paper record in database
- Creates PaperQuestion records for each generated question

### 3. Paper Review (`/faculty/paper-review/<paper_id>`)
**Features:**
- Display paper metadata (subject, difficulty, created date)
- Show statistics:
  - Total questions generated
  - Selected count (updates dynamically)
  - Total marks (updates dynamically)
- Each question displays:
  - Question text
  - Marks badge
  - Topic badge
  - Difficulty badge
- Checkbox selection for each question
- Actions:
  - Finalize Paper (submit selected questions)
  - Save Selected to Bank

**Processing:**
- Marks selected questions as `is_selected=True`
- Redirects to export page

### 4. Export Paper (`/export/<paper_id>`)
**Features:**
- PDF generation using reportlab
- Includes paper title, difficulty, date
- Lists all selected questions
- Downloads with filename: `{Subject}_paper_{id}.pdf`

### 5. Question Bank (`/faculty/question-bank`)
**Display:**
- List of all questions in database
- Each question shows:
  - Question text
  - Marks (badge)
  - Difficulty (color-coded badge)
  - Subject
  - Topic
- Search functionality (real-time filtering)
- Difficulty filter dropdown
- Actions per question:
  - Edit
  - Delete
- Empty state when no questions

### 6. Add Question (`/faculty/question-bank/add`)
**Fields:**
- Subject (required)
- Topic (required)
- Question Text (required, textarea)
- Marks (dropdown: 2/4/8)
- Difficulty (dropdown: Easy/Medium/Hard)
- Save/Cancel buttons

### 7. Edit Question (`/faculty/question-bank/edit/<q_id>`)
**Similar to Add with:**
- Pre-filled values
- Question ID display
- Update button instead of Save

### 8. Delete Question
**Action:**
- Confirmation dialog
- Deletes from database
- Redirects back to question bank

### 9. Analytics (`/faculty/analytics`)
**Statistics Displayed:**
- Total Questions (count)
- Total Papers Generated (count)
- Average Questions per Paper (calculated)
- Unique Subjects (count)

**Tables:**
- Questions by Subject (subject: count)
- Questions by Difficulty (difficulty: count)

### 10. History (`/faculty/history`)
**Table Display:**
- Paper ID
- Subject
- Difficulty (1-5 scale)
- Question Count
- Creation Date & Time
- Actions:
  - Review (link to paper-review page)
  - Download (link to export-pdf)

### 11. Settings (`/faculty/settings`)
**Sections:**

**Profile Information:**
- Name (editable)
- Email (editable)
- Password (editable, optional)
- Save button

**Preferences:**
- Email notifications for new papers (checkbox)
- Auto-save papers as drafts (checkbox)
- Show advanced options (checkbox)

**Danger Zone:**
- Delete Account button (placeholder)

## Complete User Flow

```
1. LOGIN
   ↓
2. DASHBOARD
   ├→ Quick Actions
   ├→ KPIs display
   └→ Navigation menu
   
3. PAPER GENERATOR
   ├→ Enter Subject
   ├→ Enter Syllabus
   ├→ Select Marks
   ├→ Set Difficulty
   └→ Generate
      ↓
4. PAPER REVIEW
   ├→ View Generated Questions
   ├→ Select Questions (dynamic stats update)
   └→ Finalize Paper
      ↓
5. EXPORT / SAVE
   ├→ Download PDF
   └→ Save to Question Bank
   
6. QUESTION BANK
   ├→ View All Questions
   ├→ Search & Filter
   ├→ Add New Question
   ├→ Edit Existing
   └→ Delete Question
   
7. ANALYTICS
   └→ View Statistics
   
8. HISTORY
   ├→ View Generated Papers
   ├→ Review Past Papers
   └→ Download Previous PDFs
   
9. SETTINGS
   └→ Update Profile & Preferences
```

## Database Schema Integration

### Models Used:
- **Question** (question_bank.py)
  - id, subject, topic, text, marks, difficulty
  
- **Paper** (paper.py)
  - id, subject, difficulty, created_at
  - relationship: questions (one-to-many)
  
- **PaperQuestion** (paper.py)
  - id, paper_id, topic, marks, text, is_selected
  - relationship: paper (many-to-one)

## Navigation Structure

**Persistent Sidebar:**
- Dashboard
- Question Bank
- Paper Generator
- Analytics
- History
- Settings
- Logout

**Persistent Top Bar:**
- Logo & App Title
- Semester Selector
- User Name
- Logout Button

## Key Features

1. **AI-Powered Generation**: Uses Bloom's taxonomy to create varied questions
2. **Template-Based Questions**: Multiple question patterns for each difficulty
3. **Duplicate Prevention**: Tracks used questions to avoid repetition
4. **PDF Export**: Professional paper export with reportlab
5. **Question Bank**: Central repository for all questions
6. **Analytics Dashboard**: Statistics and insights
7. **Search & Filter**: Quick access to questions
8. **History Tracking**: All generated papers are saved
9. **Responsive Design**: Works on desktop and mobile
10. **Real-time Updates**: JavaScript updates stats during selection
