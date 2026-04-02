"""Test script for duplicate detection feature"""
import sys
sys.path.insert(0, 'd:\\perproject\\2')

from app import app, db
from models.question_bank import Question

def setup_test_data():
    """Create test data with duplicates"""
    with app.app_context():
        # Clear existing test questions
        test_email = "test_faculty@example.com"
        Question.query.filter_by(owner_email=test_email).delete()
        db.session.commit()
        
        # Create test questions with duplicates
        test_questions = [
            # Group 1: 3 identical questions
            {
                "subject": "DSA",
                "topic": "Arrays",
                "text": "What is the time complexity of binary search?",
                "marks": 2,
                "difficulty": "Easy",
                "bloom_level": "Understanding",
                "co_level": "CO1"
            },
            {
                "subject": "DSA",
                "topic": "Arrays",
                "text": "What is the time complexity of binary search?",
                "marks": 2,
                "difficulty": "Easy",
                "bloom_level": "Understanding",
                "co_level": "CO1"
            },
            {
                "subject": "DSA",
                "topic": "Arrays",
                "text": "What is the time complexity of binary search?",
                "marks": 2,
                "difficulty": "Easy",
                "bloom_level": "Understanding",
                "co_level": "CO1"
            },
            # Group 2: 2 identical questions
            {
                "subject": "DSA",
                "topic": "Sorting",
                "text": "Explain the quicksort algorithm",
                "marks": 5,
                "difficulty": "Hard",
                "bloom_level": "Analyzing",
                "co_level": "CO2"
            },
            {
                "subject": "DSA",
                "topic": "Sorting",
                "text": "Explain the quicksort algorithm",
                "marks": 5,
                "difficulty": "Hard",
                "bloom_level": "Analyzing",
                "co_level": "CO2"
            },
            # Unique question
            {
                "subject": "DSA",
                "topic": "Hashing",
                "text": "What is a hash collision?",
                "marks": 3,
                "difficulty": "Medium",
                "bloom_level": "Remembering",
                "co_level": "CO1"
            },
        ]
        
        for q_data in test_questions:
            q = Question(
                subject=q_data["subject"],
                topic=q_data["topic"],
                text=q_data["text"],
                marks=q_data["marks"],
                difficulty=q_data["difficulty"],
                bloom_level=q_data["bloom_level"],
                co_level=q_data["co_level"],
                owner_email=test_email
            )
            db.session.add(q)
        
        db.session.commit()
        print(f"✅ Created {len(test_questions)} test questions")

def test_duplicate_detection():
    """Test the duplicate detection logic"""
    from routes.question_bank import _get_all_duplicates_dict, _get_duplicates_for_question
    
    with app.app_context():
        test_email = "test_faculty@example.com"
        questions = Question.query.filter_by(owner_email=test_email).all()
        
        print(f"\n📊 Total questions: {len(questions)}")
        print(f"Expected: 6 questions (3 + 2 + 1)")
        
        # Test the duplicate detection
        duplicates_map = _get_all_duplicates_dict(questions)
        
        print(f"\n🔍 Duplicates found: {len(duplicates_map)}")
        print(f"Expected: 2 duplicate groups (1 from group 1, 1 from group 2)")
        
        # Print details
        for original_id, dup_info in duplicates_map.items():
            q = Question.query.get(original_id)
            print(f"\n   Original Question ID {original_id}: '{q.text[:50]}...'")
            print(f"   - Duplicate records: {dup_info['count']}")
            print(f"   - Duplicate IDs: {dup_info['ids']}")
        
        # Validate counts
        assert len(questions) == 6, f"Expected 6 questions, got {len(questions)}"
        assert len(duplicates_map) == 2, f"Expected 2 duplicate groups in map, got {len(duplicates_map)}"
        
        # Check first duplicate group (should be 2 duplicates from 3 questions)
        first_original_id = list(duplicates_map.keys())[0]
        expected_count = 2  # 2 extra copies besides the original
        actual_count = duplicates_map[first_original_id]['count']
        assert actual_count == expected_count, f"Expected duplicate count {expected_count}, got {actual_count}"
        
        print("\n✅ All duplicate detection tests passed!")
        return True

def cleanup_test_data():
    """Remove test data"""
    with app.app_context():
        test_email = "test_faculty@example.com"
        Question.query.filter_by(owner_email=test_email).delete()
        db.session.commit()
        print("\n🧹 Cleaned up test data")

if __name__ == "__main__":
    try:
        print("=" * 60)
        print("Testing Duplicate Detection Feature")
        print("=" * 60)
        
        setup_test_data()
        test_duplicate_detection()
        cleanup_test_data()
        
        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED!")
        print("=" * 60)
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
