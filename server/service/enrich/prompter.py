

class Prompter:

    def build_prompt(self, content: str) -> str:
        prompt = f"""
            You are a Muay Thai analyst.  You have followed the sport for years and are great at 
            identifying the important statistics and memorable fights for fighters.

            - Fighting style is an important factor
            - Look for clear phases that would suggest signature weapons and attributes
            - Be sure to notice importantant career moments that would enhance the bio
            - Find something unique or interesting about this fighter that would make a good fun fact.
            - "fun_fact" should be one sentence maximum, no longer than 30 words
            - "name" should be the fighter's professional fight name, not their legal birth name
            - "nickname" should be their ring nickname or moniker (e.g. "The Iron Man"), not their legal name
            - "nickname" should only be included if it is explicitly mentioned in the provided content. 
            - "career_highlight" should be a short punchy phrase of 4-8 words maximum that captures the fighter's single most defining achievement.
                - Examples: "5x ONE Championship Title Defenses", "Longest-Reigning ONE Flyweight Champion","14-Fight WIN Streak in ONE Championship"
                - Format it like a stat callout — uppercase-friendly, no punctuation at the end.
            - If no nickname is found in the content, return null for this field. Do not invent or infer a nickname.
            - For numeric fields like record_wins, record_losses, record_kos, only use numbers explicitly stated in the content. If not clearly stated, return null.
            - Return ONLY a valid JSON object matching the example_output structure below.
            - No markdown fences, no explanation, no preamble. JSON only.

            <example_output>
            {{
                "name": "Somchai Sor Lookjaomaesai",
                "nickname": "The Southern Thunder",
                "nationality": "Thai",
                "gym": "Lookjaomaesai Gym",
                "record_wins": 187,
                "record_losses": 34,
                "record_kos": 67,
                "fighting_style": "Aggressive pressure fighter with elite clinch dominance",
                "signature_weapons": [
                    "Horizontal elbow",
                    "Knee from the clinch",
                    "Left body kick",
                    "Sweeps"
                ],
                "attributes": {{
                    "aggression": 9,
                    "power": 8,
                    "footwork": 6,
                    "clinch": 10,
                    "cardio": 9,
                    "technique": 8
                }},
                "bio": "Somchai Sor Lookjaomaesai is one of the most feared clinch fighters in the sport, having dominated the 63kg division across Thailand's major stadiums for nearly a decade. Known for his relentless forward pressure and devastating horizontal elbows, he has finished over a third of his opponents and holds notable wins over three former Lumpinee champions. His iron chin and elite cardio make him notoriously difficult to stop late in fights.",
                "fun_fact": "Somchai began training at age six and won his first professional fight at thirteen, earning enough to help his family buy their first motorcycle.",
                "career_highlight": "Longest winning streak in ONE Championship (14)"
            }}
            </example_output>

            scoring rubric for attributes:
            <rubric>
            Score attributes 1-10 where:
            - 10 = elite, world class, defining characteristic
            - 7-9 = above average, notable strength  
            - 4-6 = average, unremarkable
            - 1-3 = clear weakness
            Scores should be differentiated — not every fighter is a 9 across the board.
            </rubric>

            content to examine:
            <content>
            {content}
            </content>
        """

        return prompt
