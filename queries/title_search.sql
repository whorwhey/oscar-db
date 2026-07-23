SELECT film_id, title, release_year, imdb_id
FROM films
WHERE title LIKE ?
ORDER BY release_year;
