/**
 * schemaConverter Unit Tests — STORY-171 (AC 3 : interface canonique minimum/maximum).
 *
 * Le convertisseur consomme désormais exclusivement les bornes canoniques
 * `minimum`/`maximum` du contrat variables (divergence n°7 : module sans
 * consommateur actif — cohérence maintenue).
 */
import { describe, it, expect } from 'vitest'
import { convertToJsonSchema, extractDefaults, validateAgainstSchema } from '@/utils/schemaConverter'

describe('schemaConverter — STORY-171 bornes canoniques minimum/maximum', () => {
  describe('convertToJsonSchema', () => {
    it('mappe minimum/maximum vers property.minimum/property.maximum pour un integer', () => {
      const { schema } = convertToJsonSchema({
        host_port: {
          type: 'integer',
          label: 'Port hôte',
          default: 5432,
          minimum: 1,
          maximum: 65535,
        },
      })

      expect(schema.properties['host_port']).toBeDefined()
      expect(schema.properties['host_port']?.type).toBe('integer')
      expect(schema.properties['host_port']?.minimum).toBe(1)
      expect(schema.properties['host_port']?.maximum).toBe(65535)
    })

    it('mappe minimum/maximum vers property.minimum/property.maximum pour un number', () => {
      const { schema } = convertToJsonSchema({
        cpu_limit: {
          type: 'number',
          label: 'Limite CPU',
          default: 0.5,
          minimum: 0,
          maximum: 4,
        },
      })

      expect(schema.properties['cpu_limit']?.type).toBe('number')
      expect(schema.properties['cpu_limit']?.minimum).toBe(0)
      expect(schema.properties['cpu_limit']?.maximum).toBe(4)
    })

    it("active l'option slider quand les deux bornes sont présentes sur un number", () => {
      const { uischema } = convertToJsonSchema({
        cpu_limit: {
          type: 'number',
          label: 'Limite CPU',
          default: 0.5,
          minimum: 0,
          maximum: 4,
        },
      })

      const control = uischema.elements[0] as { options?: { slider?: boolean } }
      expect(control.options?.slider).toBe(true)
    })

    it("n'active pas l'option slider quand une borne manque", () => {
      const { uischema } = convertToJsonSchema({
        cpu_limit: {
          type: 'number',
          label: 'Limite CPU',
          default: 0.5,
          minimum: 0,
        },
      })

      const control = uischema.elements[0] as { options?: { slider?: boolean } }
      expect(control.options?.slider).toBeUndefined()
    })

    it("n'active pas le slider pour un integer même borné", () => {
      const { uischema } = convertToJsonSchema({
        host_port: {
          type: 'integer',
          label: 'Port hôte',
          default: 5432,
          minimum: 1,
          maximum: 65535,
        },
      })

      const control = uischema.elements[0] as { options?: { slider?: boolean } }
      expect(control.options?.slider).toBeUndefined()
    })

    it('min_length/max_length/pattern restent inchangés pour un string', () => {
      const { schema } = convertToJsonSchema({
        db_password: {
          type: 'password',
          label: 'Mot de passe',
          default: 's3cr3t!',
          required: true,
          min_length: 12,
          max_length: 64,
          pattern: '^[A-Za-z0-9!@#$%^&*]+$',
        },
      })

      const prop = schema.properties['db_password']
      expect(prop?.type).toBe('string')
      expect(prop?.minLength).toBe(12)
      expect(prop?.maxLength).toBe(64)
      expect(prop?.pattern).toBe('^[A-Za-z0-9!@#$%^&*]+$')
      expect(schema.required).toContain('db_password')
    })

    it('des bornes legacy min/max sont ignorées (plus lues — AC 3)', () => {
      const { schema, uischema } = convertToJsonSchema({
        host_port: {
          type: 'integer',
          label: 'Port hôte',
          default: 5432,
          // Payload legacy pré-STORY-171 : ne doit plus influencer la sortie
          min: 70000,
          max: 99999,
        } as never,
      })

      expect(schema.properties['host_port']?.minimum).toBeUndefined()
      expect(schema.properties['host_port']?.maximum).toBeUndefined()

      const control = uischema.elements[0] as { options?: { slider?: boolean } }
      expect(control.options?.slider).toBeUndefined()
    })
  })

  describe('extractDefaults', () => {
    it('extrait les défauts numériques coercés', () => {
      const { schema } = convertToJsonSchema({
        host_port: { type: 'integer', label: 'Port hôte', default: '5432', minimum: 1, maximum: 65535 },
      })

      const defaults = extractDefaults(schema)
      expect(defaults['host_port']).toBe(5432)
    })
  })

  describe('validateAgainstSchema', () => {
    it('valide les bornes minimum/maximum du JSON Schema généré', () => {
      const { schema } = convertToJsonSchema({
        host_port: { type: 'integer', label: 'Port hôte', default: 5432, minimum: 1, maximum: 65535 },
      })

      const below = validateAgainstSchema({ host_port: 0 }, schema)
      expect(below.valid).toBe(false)
      expect(below.errors.some((e) => e.includes('>= 1'))).toBe(true)

      const above = validateAgainstSchema({ host_port: 70000 }, schema)
      expect(above.valid).toBe(false)
      expect(above.errors.some((e) => e.includes('<= 65535'))).toBe(true)

      const within = validateAgainstSchema({ host_port: 5432 }, schema)
      expect(within.valid).toBe(true)
    })

    it('valide pattern et longueurs pour un string', () => {
      const { schema } = convertToJsonSchema({
        db_password: {
          type: 'password',
          label: 'Mot de passe',
          required: true,
          min_length: 12,
          pattern: '^[A-Za-z0-9]+$',
        },
      })

      // 'short!' : trop court (6 < 12) ET contient '!' qui viole le pattern
      const result = validateAgainstSchema({ db_password: 'short!' }, schema)
      expect(result.valid).toBe(false)
      expect(result.errors.some((e) => e.includes('au moins 12 caractères'))).toBe(true)
      expect(result.errors.some((e) => e.includes('format attendu'))).toBe(true)
    })
  })
})
