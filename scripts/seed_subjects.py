import asyncio
import re

from sqlalchemy import select

import app.db.model_registry  # noqa: F401
from app.core.database import AsyncSessionFactory, engine
from app.domain.subjects.models.subject import Subject

SUBJECTS = {
    "Academic Subjects": [
        "Mathematics",
        "Further Mathematics",
        "English Language",
        "English Literature",
        "Basic Science",
        "Basic Technology",
        "Physics",
        "Chemistry",
        "Biology",
        "Agricultural Science",
        "Geography",
        "History",
        "Government",
        "Civic Education",
        "Economics",
        "Commerce",
        "Accounting",
        "Financial Accounting",
        "Business Studies",
        "Social Studies",
        "Computer Studies",
        "Computer Science",
        "Physical and Health Education",
        "Religious Studies",
        "Christian Religious Studies",
        "Islamic Religious Studies",
        "Home Economics",
        "Food and Nutrition",
        "Literature in English",
        "Technical Drawing",
        "Statistics",
        "Environmental Science",
        "Philosophy",
    ],
    "Early Childhood and Primary Education": [
        # Early childhood
        "Early Childhood Education",
        "Nursery Education",
        "Kindergarten Education",
        "School Readiness",
        # Literacy and English
        "Phonics",
        "Reading and Literacy",
        "Reading Comprehension",
        "English Studies",
        "English Language Development",
        "English Grammar",
        "Oral English",
        "Spelling and Vocabulary",
        "Creative Writing",
        "Composition Writing",
        "Handwriting",
        "Handwriting and Penmanship",
        # Mathematics and numeracy
        "Numeracy",
        "Primary School Mathematics",
        "Number Work",
        "Mental Mathematics",
        "Basic Arithmetic",
        "Measurement",
        "Geometry",
        "Problem Solving for Children",
        # Primary curriculum subjects
        "Primary School English",
        "Primary School Science",
        "Basic Science and Technology",
        "National Values Education",
        "Cultural and Creative Arts",
        "Pre-vocational Studies",
        "Nigerian Languages",
        "Local Language Literacy",
        "Primary School Social Studies",
        "Primary School Civic Education",
        "Primary School Computer Studies",
        "Primary School Agricultural Science",
        "Primary School Home Economics",
        "Primary School Religious Studies",
        "Primary School Physical and Health Education",
        "Primary School French",
        # General development
        "General Knowledge",
        "Environmental Studies",
        "Health and Hygiene",
        "Safety Education",
        "Moral Education",
        "Creative Arts",
        "Drawing and Painting",
        "Music for Children",
        "Social and Emotional Learning",
        "Study Skills for Children",
        # Learning support
        "Primary School Preparation",
        "Common Entrance Examination Preparation",
        "Primary School Homework Support",
        "Primary School Exam Preparation",
        "Learning Difficulties Support",
    ],
    "Technology and Programming": [
        "Computer Programming",
        "Python Programming",
        "JavaScript Programming",
        "TypeScript Programming",
        "Java Programming",
        "C Programming",
        "C++ Programming",
        "C# Programming",
        "PHP Programming",
        "Go Programming",
        "Rust Programming",
        "Web Development",
        "Frontend Development",
        "Backend Development",
        "Full-Stack Development",
        "Mobile App Development",
        "Android Development",
        "iOS Development",
        "React",
        "Next.js",
        "Node.js",
        "Django",
        "FastAPI",
        "Database Management",
        "SQL",
        "PostgreSQL",
        "Data Structures and Algorithms",
        "Software Engineering",
        "Artificial Intelligence",
        "Machine Learning",
        "Data Science",
        "Data Analytics",
        "Cybersecurity",
        "Cloud Computing",
        "DevOps",
        "UI Development",
        "Game Development",
        "Robotics",
        "Computer Networking",
        "Microsoft Office",
        "Microsoft Excel",
        "Power BI",
        "Digital Literacy",
    ],
    "Languages": [
        "English as a Second Language",
        "French",
        "Spanish",
        "German",
        "Portuguese",
        "Arabic",
        "Chinese (Mandarin)",
        "Japanese",
        "Korean",
        "Igbo",
        "Yoruba",
        "Hausa",
        "Swahili",
        "Sign Language",
        "English Communication",
        "Business English",
        "English Grammar",
        "Public Speaking",
    ],
    "Business and Professional Development": [
        "Business Management",
        "Entrepreneurship",
        "Project Management",
        "Product Management",
        "Human Resource Management",
        "Marketing",
        "Digital Marketing",
        "Social Media Marketing",
        "Sales",
        "Customer Service",
        "Business Communication",
        "Leadership and Management",
        "Financial Management",
        "Bookkeeping",
        "Business Analysis",
        "Data Analysis for Business",
        "Strategic Management",
        "Supply Chain Management",
        "Operations Management",
        "Public Administration",
        "Research Methods",
        "Professional Writing",
        "Grant Writing",
        "CV and Resume Writing",
        "Interview Preparation",
        "Career Development",
    ],
    "Creative Arts and Design": [
        "Graphic Design",
        "UI/UX Design",
        "Web Design",
        "Product Design",
        "Fashion Design",
        "Interior Design",
        "Architecture",
        "Drawing",
        "Painting",
        "Illustration",
        "Photography",
        "Videography",
        "Video Editing",
        "Animation",
        "3D Modelling",
        "Motion Graphics",
        "Content Creation",
        "Creative Writing",
        "Script Writing",
        "Music Theory",
        "Piano",
        "Guitar",
        "Drums",
        "Singing",
        "Music Production",
        "Dance",
        "Acting",
    ],
    "Vocational and Practical Skills": [
        "Fashion Design and Tailoring",
        "Hairdressing",
        "Barbing",
        "Makeup Artistry",
        "Cosmetology",
        "Catering",
        "Baking",
        "Pastry Making",
        "Event Planning",
        "Carpentry",
        "Furniture Making",
        "Welding",
        "Plumbing",
        "Electrical Installation",
        "Electronics Repair",
        "Phone Repair",
        "Computer Repair",
        "Automobile Mechanics",
        "Refrigeration and Air Conditioning",
        "Solar Installation",
        "Interior Decoration",
        "Upholstery",
        "Agricultural Production",
        "Poultry Farming",
        "Fish Farming",
        "Crop Production",
        "Animal Husbandry",
        "Food Processing",
        "Soap Making",
        "Bead Making",
        "Craft Making",
    ],
    "Agriculture and Environmental Studies": [
        "Agricultural Engineering",
        "Crop Science",
        "Soil Science",
        "Animal Science",
        "Agricultural Economics",
        "Agricultural Extension",
        "Horticulture",
        "Aquaculture",
        "Forestry",
        "Agribusiness",
        "Irrigation and Water Management",
        "Food Science and Technology",
        "Environmental Management",
        "Climate Change Studies",
        "Sustainable Agriculture",
        "Agricultural Technology",
    ],
    "Personal Development and Learning": [
        "Study Skills",
        "Time Management",
        "Critical Thinking",
        "Problem Solving",
        "Communication Skills",
        "Emotional Intelligence",
        "Memory and Learning Techniques",
        "Leadership Skills",
        "Negotiation Skills",
        "Confidence Building",
        "Reading Skills",
        "Speed Reading",
        "Presentation Skills",
        "Financial Literacy",
        "Personal Finance",
    ],
}


def slugify(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")


async def main():
    added = 0
    skipped = 0

    try:
        async with AsyncSessionFactory() as db:
            result = await db.execute(select(Subject.name, Subject.slug))
            existing_records = result.all()

            existing_names = {name.strip().casefold() for name, _ in existing_records}
            existing_slugs = {slug for _, slug in existing_records}

            for category, names in SUBJECTS.items():
                for name in names:
                    slug = slugify(name)

                    if name.casefold() in existing_names or slug in existing_slugs:
                        skipped += 1
                        continue

                    subject = Subject(
                        name=name,
                        slug=slug,
                        description=f"{category} learning area.",
                        is_active=True,
                    )

                    db.add(subject)

                    existing_names.add(name.casefold())
                    existing_slugs.add(slug)

                    added += 1

            await db.commit()

            print("\nSubject seeding completed successfully.")
            print(f"Added:   {added}")
            print(f"Skipped: {skipped}")
            print(f"Total:   {added + skipped}")

    except Exception:
        raise

    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
