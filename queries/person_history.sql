SELECT p.person_id, p.name, c.year_label, cat.award_group,
       n.official_name, n.is_winner
FROM nominations n
JOIN nomination_people np ON n.nomination_id = np.nomination_id
JOIN people p ON np.person_id = p.person_id
JOIN ceremonies c ON n.ceremony = c.ceremony
JOIN categories cat ON n.category_id = cat.category_id
WHERE p.name LIKE ?
ORDER BY p.person_id, c.ceremony;
